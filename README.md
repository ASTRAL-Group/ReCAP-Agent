<div align="center">

# CAPTCHA-Capable GUI Agent

[![Project](https://img.shields.io/badge/arxiv-pending-red)](#)
![Dataset](https://img.shields.io/badge/huggingface-pending-orange?logo=huggingface&logoColor=yellow)
![Status](https://img.shields.io/badge/python-3.11+-blue)
![Lisence](https://img.shields.io/badge/Lisense-MIT-orange)


</div>

This repository contains the main artifacts for our paper on training stronger CAPTCHA-capable GUI agents (ReCAP).
It combines:
- dynamic CAPTCHA generation,
- real-world/static CAPTCHA benchmarks,
- a unified evaluation framework across providers and model families,
- and (incoming) trace generation pipelines.

## Motivation

Modern GUI/web agents are often blocked by CAPTCHA gates in real workflows.
This project provides a practical stack to:
- build and serve diverse CAPTCHA tasks,
- benchmark agent performance in a reproducible way,
- and generate reasoning-action plus self-correction supervision traces for improved training.

Concretely, the project follows the ReCAP setup: a CAPTCHA-capable native GUI agent trained with automated reasoning-action data generation and corrective traces from failed attempts. The dynamic CAPTCHA system covers seven representative interactive types (`text`, `compact text`, `icon match`, `icon selection`, `paged`, `slider`, `image grid`) to encourage transfer across diverse layouts and interaction patterns.

## Components

1. `dynamic_captchas/`  
   Designed and benchmarked dynamic CAPTCHAs used in this project.
   See [Dynamic CAPTCHAs Documentation](./dynamic_captchas/README.md) for more details on the CAPTCHA types, server setup, and evaluation usage.

2. `halligan_captchas/`  
   This CAPTCHA challenge set is part of the paper ["Are CAPTCHAs Still Bot-hard? Generalized Visual CAPTCHA Solving with Agentic Vision Language Model"](https://www.usenix.org/conference/usenixsecurity25/presentation/teoh) and copied into this repository for ease of access. See [Halligan CAPTCHAs Documentation](./halligan_captchas/README.md) for details on the benchmark setup, CAPTCHA types, and evaluation usage.

3. `captcha_eval_framework/`  
   Unified platform for evaluating different CAPTCHA providers with different model backbones. See [CAPTCHA Evaluation Framework](./captcha_eval_framework/README.md) for details on configuration, usage, and reproducibility best practices.

4. `trace_generation/` (Incoming)  
   Pipelines for generating reasoning-action trajectories and self-correction traces from evaluation runs. This module will include scripts to process successful and failed runs, extract relevant data, and format it for training supervision.

### Project Layout

```text
captcha-capable-gui-agent/
├── dynamic_captchas/
├── halligan_captchas/
├── captcha_eval_framework/
├── trace_generation/
└── README.md
```

## End-to-End Workflow

1. Run a CAPTCHA provider server.
2. Configure provider URL(s) and model API settings in the evaluation framework.
3. Execute benchmark runs with selected provider, test mode, and model family.
4. Generate/collect reasoning-action trajectories (successful and failed).
5. Build self-correction traces from failed runs (incoming module).
6. Compare runs with `runs/<timestamp>/` artifacts and iterate on training/evaluation.

## Quick Start

1. Start Dynamic CAPTCHA server:

```bash
cd dynamic_captchas
pip install -r requirements.txt
python download_datasets.py
python app.py
```

2. Start Halligan benchmark server

```bash
cd halligan_captchas
conda env create --file environment.yml --name halligan-benchmark
conda activate halligan-benchmark
python server.py
```

3. Run evaluation:

```bash
cd captcha_eval_framework
pip install -r requirements.txt
cp .env.example .env
python3 ./main.py --provider dynamic --test-mode once --model-family qwen3
```

Please refer to the respective component READMEs for more detailed instructions, configuration options, and troubleshooting tips.

## Roadmap

- [x] Dynamic CAPTCHA generation and verification server
- [x] Static benchmark integration
- [x] Unified cross-provider evaluation framework
- [ ] Trace generation module (regular + self-correction traces)

## Contributing

Contributions to this project are welcome! Please follow these steps:
1. Fork the repository and create a new branch for your feature or bug fix.
2. Make your changes and commit them with clear messages.
3. Push your changes to your forked repository.
4. Open a pull request to the main repository with a detailed description of your changes.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
