# Unified CAPTCHA Testing Framework

Unified CAPTCHA Testing Framework is a parallel browser-testing framework for evaluating GUI Agents/Computer Use Agents on CAPTCHA tasks.

### What It Does

For each task, the runner:
1. Opens a CAPTCHA page in a Playwright-controlled browser.
2. Captures a screenshot.
3. Sends prompt + image to the selected model backend.
4. Parses model output into executable UI actions.
5. Executes actions in browser.
6. Repeats until CAPTCHA solved or max calls reached.
7. Saves per-run logs, images, and JSON summary.

## Quick Start
1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Configure environment variables in `./.env` (copy from `.env.example`).

3. Run the benchmark with desired arguments. The results will be saved in `runs/<timestamp>/` with logs, screenshots, and summary JSON. For example:

```bash
python3 ./main.py --provider dynamic --test-mode complete --model-family qwen3
```

## Arguments

- `--provider`: CAPTCHA provider to run against (e.g., `dynamic`)
- `--test-mode`: testing mode, determines task selection and iteration logic (e.g., `once`)
- `--model-family`: model family (determines parser + prompt + backend)
- `--workers`: parallel browser workers
- `--captcha-name`: optional, run only a named captcha type in `custom` mode
- `--test-size`: optional, run named captcha type `test-size` times in in `custom` mode
- `--seed`: optional, sampling seed

### Provider

- `dynamic`: dynamically generated CAPTCHAs (image grid, paged, etc.) with visual variety and unbounded sample space. For more info please refer to [Dynamic CAPTCHAs Documentation](../dynamic_captchas/README.md).

- `halligan`: static set of real-world CAPTCHAs (e.g. reCAPTCHA v2, hCaptcha, Arkose, MTCaptcha) from Halligan provider. Each captcha type has a 100 samples. For more info please refer to the paper: [Are CAPTCHAs Still Bot-Hard? Generalized Visual CAPTCHA Solving with Agentic Vision Language Models](https://www.usenix.org/conference/usenixsecurity25/presentation/teoh).

### Test Mode

`once`: every supported captcha type once.

`complete`: exhaustive over all available samples for supported captcha types. For unbounded providers like `dynamic`, runs for a fixed large number of iterations (e.g., 1000) and reports aggregate stats.

`custom`: user-defined subset of tasks, determined by `--captcha-name` and `--test-size`.

Examples:

```bash

# Under Dynamic CAPTCHA provider, run test on 1,000 CAPTCHAs, using UI-TARS model family
python3 ./main.py --provider dynamic --test-mode complete --model-family ui-tars

# Under Halligan CAPTCHA provider, run test once per each captcha type, using qwen3 model family
python3 ./main.py --provider halligan --test-mode once --model-family qwen3

# Under Dynamic CAPTCHA provider, test 30 paged CAPTCHA samples, using qwen3 model family
python3 ./main.py --provider dynamic --test-mode custom --captcha-name paged --test-size 30 --model-family qwen3

# Under Halligan CAPTCHA provider, run test on 50 samples from all captcha types (set seed=42 for sampling), using qwen3 model family
python3 ./main.py --provider halligan --test-mode custom --test-size 50 --seed 42 --model-family qwen3
```

### Model Family

Model family specify the model used for testing, as well as the associated prompt and response parser. The framework is designed to be modular and extensible, allowing easy addition of new model families with their own parsers and prompts. Currently, the framework supports the following model families:

- `qwen3`: Qwen3-VL series model.
- `ui-tars`: UI-TARS-1.5 series model.
- `openai-cua`: OpenAI's Computer Use Agent.

## Configuration

Runtime configuration is loaded from `.env` file and can be overridden by environment variables. To set up the .env file, run:

```bash
cp ./.env.example ./.env
```

Common settings:
- Model/API: `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL`, `OPENAI_CUA_MODEL`
- Browser: `BROWSER_HEADLESS`, `BROWSER_VIEWPORT_WIDTH`, `BROWSER_VIEWPORT_HEIGHT`, `BROWSER_SLOW_MO`
- Runner: `MAX_CALLS`, `TEST_MODE`, `TEST_SIZE`, `TEST_SEED`, `RUNS_DIR`, `LOG_LEVEL`
- Providers: `HALLIGAN_PROVIDER_URL`, `DYNAMIC_PROVIDER_URL`

## Output Artifacts

Each run writes to:

```text
runs/<timestamp>/
```

Files:
- `run-configuration.json`: resolved CLI/runtime config for the run
- `captcha-benchmark-results.json`: aggregate stats + per-task records
- `unified-benchmark-test.log`: execution log (includes final summary table)
- `img/test_<task_id>.png`: screenshots for each captcha task


## Extending the Framework

### Add a New Provider

1. Create a provider adapter in `providers/`, for example `providers/my_provider.py`.
2. Subclass `CaptchaProvider` from [`providers/base.py`](./providers/base.py) and set a unique `name`.
3. Implement required methods:
   - `build_tasks(...) -> List[CaptchaTask]`
   - `open_task(page, task)`
   - `capture_task(page, task)`
   - `check_solved(page, task)`
4. Implement optional hooks if needed:
   - `prepare_task(...)` for pre-click/frame setup
   - `resolve_task(...)` to set `resolved_type`/metadata
   - `get_max_calls(...)` for provider-specific max-call override
   - `capture_final(...)` for custom final screenshots
5. Register the provider by importing it in [`providers/__init__.py`](./providers/__init__.py). The metaclass registry auto-registers by class `name`.
6. If you add new provider URLs/config, add env keys in [`utils.py`](./utils.py) and mirror them in `.env.example`.
7. Smoke test with CLI using `--provider <your-name>`.

Minimal template:

```python
from typing import List, Optional
from actions import CaptchaTask
from providers.base import CaptchaProvider

class MyProvider(CaptchaProvider):
    name = "my-provider"
    expects_submit_response = False

    def build_tasks(self, test_mode: str, test_size: Optional[int], seed: Optional[int], captcha_name: Optional[str]) -> List[CaptchaTask]:
        return [CaptchaTask(self.name, "example", attempt=1)]

    async def open_task(self, page, task: CaptchaTask) -> None:
        await page.goto("http://localhost:9999/challenge")

    async def capture_task(self, page, task: CaptchaTask):
        screenshot = await page.screenshot()
        from io import BytesIO
        from PIL import Image
        image = Image.open(BytesIO(screenshot))
        return image, image.size[0], image.size[1]

    async def check_solved(self, page, task: CaptchaTask):
        return False
```

### Add a New Parser (and Model Family)

1. Create a parser in `parsers/`, for example `parsers/my_parser.py`.
2. Subclass `ActionParser` from [`parsers/base.py`](./parsers/base.py) and implement `parse_response(self, response: str) -> List[Action]`.
3. Return `Action` objects using executor-supported action types (see list below).
4. Set `coord_mode` correctly (`absolute`, `relative`, or `grid`) so validation/conversion works as expected.
5. Export/import the parser in [`parsers/__init__.py`](./parsers/__init__.py).
6. Add a model profile entry in [`model_profiles.py`](./model_profiles.py) that wires:
   - `agent_factory` (e.g., `GPTAgent` or `CUAAgent`)
   - `parser_factory` (usually `CompositeActionParser([YourParser()])`)
   - base/subsequent prompts from [`prompt.py`](./prompt.py)
7. Run with `--model-family <your-family>`.

Minimal parser template:

```python
from typing import List
from actions import Action
from parsers.base import ActionParser

class MyActionParser(ActionParser):
    name = "my-parser"

    def parse_response(self, response: str) -> List[Action]:
        # Convert model output text/json into executable actions
        return [Action(type="click", x=200, y=300, coord_mode="absolute", description=response)]
```
