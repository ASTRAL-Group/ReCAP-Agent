#!/usr/bin/env python3
"""CLI entry point for the CAPTCHA evaluation framework."""

from __future__ import annotations
import argparse
import json
import os

from model_profiles import MODEL_PROFILES, get_model_profile
from prompt_processor import PromptProcessor
from runner import BenchmarkRunner, build_run_timestamp
from providers.base import CaptchaProviderMeta
import providers  # noqa: F401
from utils import (
    MAX_CALLS,
    RUNS_DIR,
    TEST_MODE,
    TEST_SIZE,
    resolve_seed,
    setup_logging,
    validate_runtime_config,
)

DEFAULT_WORKERS = max(1, min(4, os.cpu_count() or 4))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unified CAPTCHA Benchmark")
    parser.add_argument(
        "--provider",
        choices=sorted(CaptchaProviderMeta.registry.keys()),
        default="halligan",
        help="CAPTCHA provider to use",
    )
    parser.add_argument(
        "--test-mode",
        choices=["once", "complete", "custom"],
        default=TEST_MODE,
        help="Test mode selection",
    )
    parser.add_argument(
        "--test-size",
        type=int,
        default=TEST_SIZE,
        help="Task count for custom mode (required semantics for custom)",
    )
    parser.add_argument("--seed", type=int, default=resolve_seed())
    parser.add_argument("--captcha-name", type=str, default=None)
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help="Number of parallel browser workers",
    )
    parser.add_argument(
        "--model-family",
        choices=sorted(MODEL_PROFILES.keys()),
        required=True,
        help="Model family used for prompt/parser/backend selection",
    )
    return parser.parse_args()


def write_run_config(run_dir: str, args: argparse.Namespace, provider_name: str) -> str:
    config_data = {
        "run_info": {
            "run_directory": run_dir,
            "provider": provider_name,
        },
        "test_configuration": {
            "test_mode": args.test_mode,
            "test_size": args.test_size,
            "seed": args.seed,
            "captcha_name": args.captcha_name,
            "max_calls": MAX_CALLS,
        },
        "execution": {
            "workers": args.workers,
            "model_family": args.model_family,
        },
    }

    path = os.path.join(run_dir, "run-configuration.json")
    with open(path, "w") as handle:
        json.dump(config_data, handle, indent=2)
    return path


def main() -> None:
    args = parse_args()
    if args.test_mode == "custom" and args.test_size < 1:
        raise SystemExit("--test-size must be >= 1 for custom mode")
    validate_runtime_config(args.model_family)

    run_timestamp = build_run_timestamp()
    run_dir = os.path.join(RUNS_DIR, run_timestamp)
    setup_logging(run_timestamp=run_timestamp)
    os.makedirs(run_dir, exist_ok=True)

    provider_cls = CaptchaProviderMeta.registry.get(args.provider)
    if not provider_cls:
        raise SystemExit(f"Unknown provider adapter: {args.provider}")
    provider = provider_cls()

    tasks = provider.build_tasks(
        test_mode=args.test_mode,
        test_size=args.test_size,
        seed=args.seed,
        captcha_name=args.captcha_name,
    )

    if not tasks:
        raise SystemExit("No tasks generated. Check your selection options.")

    profile = get_model_profile(args.model_family)
    parser = profile.parser_factory()
    agent_factory = profile.agent_factory
    prompt_processor_factory = lambda: PromptProcessor(
        base_prompt=profile.base_prompt,
        subsequent_prompt=profile.subsequent_prompt,
    )

    write_run_config(run_dir, args, args.provider)

    runner = BenchmarkRunner(
        server=provider,
        agent_factory=agent_factory,
        parser=parser,
        workers=max(1, args.workers),
        run_timestamp=run_timestamp,
        max_calls=max(1, MAX_CALLS),
        prompt_processor_factory=prompt_processor_factory,
    )

    summary = asyncio_run(runner.run(tasks))
    _ = summary


def asyncio_run(coro):
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        return asyncio.create_task(coro)
    return asyncio.run(coro)


if __name__ == "__main__":
    main()
