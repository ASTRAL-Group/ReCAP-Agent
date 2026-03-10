# Trace Generation

Trace generation utilities for ReCAP-Agent training data construction. It works with Dynamic CAPTCHAs module and produces rich raw trace JSON. It also coomes with conversion utility to transform it to model-specific training formats.

## Generation Modes

### 1. Direct Trace Generation (`trace_generation direct`)

- Uses deterministic solvers to generate ground-truth actions.
- Uses the reasoning model to generate thought traces for those actions.

### 2. Self-Correction Generation (`trace_generation self-correction`)

- Uses the actor model for an initial attempt.
- If the attempt succeeds, the sample is skipped (not stored).
- If the attempt fails, the pipeline:
  - computes ground-truth recovery actions with solvers,
  - calls the reasoning model on the current failed state,
  - stores correction reasoning + ground-truth recovery actions.

### 3. Data Format Conversion (`trace_generation convert`)

Generates model-specific training data formats from raw trace JSON files. 
Supported conversion targets:

- `qwen3` (`<tool_call>` format)
- `ui-tars` + `relative` coordinates (`<point>` format)
- `ui-tars` + `absolute` coordinates (`<relative-point>` format)

## Quick Start

### 1. Start Dynamic CAPTCHA server

```bash
cd dynamic_captchas
pip install -r requirements.txt
python download_datasets.py
python app.py
```

### 2. Install runtime dependencies

```bash
pip install -r captcha_eval_framework/requirements.txt
python -m playwright install chromium
```

### 3. Configure environment variables

Actor model variables (used by self-correction initial attempts):

- `ACTOR_API_KEY`
- `ACTOR_BASE_URL`
- `ACTOR_MODEL`

Reasoning model variables (used by direct + correction reasoning):

- `REASONER_API_KEY`
- `REASONER_BASE_URL` (default: `https://api.openai.com/v1`)
- `REASONER_MODEL`
- optional: `REASONER_MAX_OUTPUT_TOKENS` (default: `1000`)
- optional: `REASONER_MAX_ATTEMPTS` (default: `2`)


Example Configuration:

```bash
export ACTOR_BASE_URL=http://localhost:8000/v1
export ACTOR_API_KEY=EMPTY
export ACTOR_MODEL=Qwen/Qwen3-VL-8B-Instruct

export REASONER_BASE_URL=https://api.openai.com/v1
export REASONER_API_KEY=<your-openai-key>
export REASONER_MODEL=gpt-5.2
```

4. Start Trace Generation

```bash
python trace_generation direct
python trace_generation self-correction
python trace_generation convert
```

## Usage

### Supported Challenge Types

- `text`
- `compact_text`
- `icon_selection`
- `paged`
- `icon_match`
- `slider`
- `image_grid`

### 1. Generate Direct Traces

```bash
python -m trace_generation direct --num-samples 30 --challenge-type image_grid
```

Interactive mode:

```bash
python -m trace_generation direct -I
```

### 2. Generate Self-Correction Traces

```bash
python -m trace_generation self-correction --num-samples 20 --max-attempts 200
```

Interactive mode:

```bash
python -m trace_generation self-correction -I
```

### 3. Convert One File (Interactive)

```bash
python -m trace_generation convert
```

### 4. Optional: Convert One File (Non-Interactive)

```bash
python -m trace_generation convert \
  --input runs/<run_id>/conversations.json \
  --format qwen3
```

## Examples

### Example 1: Generate direct traces, then convert to Qwen3

```bash
python -m trace_generation direct --num-samples 50 --challenge-type image_grid --workers 4
python -m trace_generation convert --input runs/<run_id>/conversations.json --format qwen3
```

Produces:

- `runs/<run_id>/conversations.json`
- `runs/<run_id>/conversations_sharegpt_qwen3.json`

### Example 2: Convert to UI-TARS relative format

```bash
python -m trace_generation convert --input runs/<run_id>/conversations.json --format ui-tars-relative
```

Produces `*_sharegpt_ui_tars_relative.json`.

### Example 3: Convert to UI-TARS absolute format

```bash
python -m trace_generation convert --input runs/<run_id>/conversations.json --format ui-tars-absolute
```

Produces `*_sharegpt_ui_tars_absolute.json`.

### Example 4: Collect failed self-correction samples

```bash
python -m trace_generation self-correction --num-samples 25 --max-attempts 250 --challenge-type paged
```

Produces:

- `runs/<run_id>/self_correction_conversations.json`
- `runs/<run_id>/stats.json`

## Output Artifacts

Each run writes to:

```text
runs/<run_id>/
```

Common files:

- raw traces: `conversations.json` or `self_correction_conversations.json`
- converted traces: `*_sharegpt_qwen3.json`, `*_sharegpt_ui_tars_relative.json`, `*_sharegpt_ui_tars_absolute.json`
- screenshots: `img/`
- self-correction stats: `stats.json`

