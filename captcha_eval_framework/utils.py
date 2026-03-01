#!/usr/bin/env python3
"""Shared utility helpers and configurations for the CAPTCHA evaluation framework."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
import logging
import os
from typing import Dict, List, Optional

from actions import TaskResult


def _load_dotenv() -> None:
    """Load .env values into os.environ without overriding existing env."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        return

    try:
        with open(env_path, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if not key:
                    continue

                if value and value[0] == value[-1] and value[0] in {"'", '"'}:
                    value = value[1:-1]

                os.environ.setdefault(key, value)
    except OSError:
        return


_load_dotenv()

# Model configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "Qwen/Qwen3-VL-8B-Instruct")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "http://localhost:8000/v1")
MODEL_MAX_COMPLETION_TOKENS = int(os.getenv("MODEL_MAX_COMPLETION_TOKENS", "1024"))
MODEL_TEMPERATURE = float(os.getenv("MODEL_TEMPERATURE", "0.7"))
MODEL_TOP_P = float(os.getenv("MODEL_TOP_P", "0.8"))
OPENAI_CUA_MODEL = os.getenv("OPENAI_CUA_MODEL", "computer-use-preview")
OPENAI_CUA_ENVIRONMENT = os.getenv("OPENAI_CUA_ENVIRONMENT", "browser")
OPENAI_CUA_REASONING_SUMMARY = os.getenv("OPENAI_CUA_REASONING_SUMMARY", "")

# Provider endpoints
HALLIGAN_PROVIDER_URL = os.getenv("HALLIGAN_PROVIDER_URL", "http://localhost:3334")
DYNAMIC_PROVIDER_URL = os.getenv("DYNAMIC_PROVIDER_URL", "http://localhost:5000")

# Browser configuration
BROWSER_HEADLESS = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
BROWSER_VIEWPORT = {
    "width": int(os.getenv("BROWSER_VIEWPORT_WIDTH", "1200")),
    "height": int(os.getenv("BROWSER_VIEWPORT_HEIGHT", "800")),
}
BROWSER_SLOW_MO = int(os.getenv("BROWSER_SLOW_MO", "50"))

# Timing configuration (ms)
ACTION_DELAY_MS = int(os.getenv("ACTION_DELAY_MS", "150"))
POST_ACTION_DELAY_MS = int(os.getenv("POST_ACTION_DELAY_MS", "400"))
HALLIGAN_RESPONSE_TIMEOUT = int(os.getenv("HALLIGAN_RESPONSE_TIMEOUT", "800"))

# Runner configuration
RUNS_DIR = os.getenv("RUNS_DIR", "runs")
LOG_LEVEL = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
MAX_CALLS = int(os.getenv("MAX_CALLS", "4"))
TEST_MODE = os.getenv("TEST_MODE", "once")
TEST_SIZE = int(os.getenv("TEST_SIZE", "2"))
TEST_SEED = os.getenv("TEST_SEED")

_logging_configured = False
_file_handler: Optional[logging.Handler] = None


def setup_logging(run_timestamp: Optional[str] = None, log_file_path: Optional[str] = None) -> None:
    """Set up centralized logging configuration for all modules."""
    global _logging_configured, _file_handler

    if _logging_configured:
        return

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    if run_timestamp or log_file_path:
        if log_file_path:
            log_file = log_file_path
        else:
            os.makedirs(f"{RUNS_DIR}/{run_timestamp}", exist_ok=True)
            log_file = f"{RUNS_DIR}/{run_timestamp}/unified-benchmark-test.log"

        _file_handler = logging.FileHandler(log_file)
        _file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    if _file_handler:
        root_logger.addHandler(_file_handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    _logging_configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger instance for a module."""
    return logging.getLogger(name)


def resolve_seed() -> Optional[int]:
    if TEST_SEED is None:
        return None
    try:
        return int(TEST_SEED)
    except ValueError:
        return None


def validate_runtime_config(model_family: str) -> None:
    """Fail fast on missing critical runtime configuration."""
    required_openai_families = {"qwen3", "ui-tars", "openai-cua"}
    if model_family in required_openai_families and not OPENAI_API_KEY:
        raise SystemExit(
            "OPENAI_API_KEY is required for model family "
            f"'{model_family}'. Set it in environment or .env."
        )


def summarize_results(task_results: List[TaskResult]) -> Dict:
    """Aggregate task-level outcomes into benchmark summary stats."""
    results_by_type: Dict[str, Dict] = {}
    overall_total = len(task_results)
    overall_solved = 0
    solve_steps: List[int] = []

    grouped: Dict[str, List[TaskResult]] = defaultdict(list)
    for result in task_results:
        grouped[result.resolved_type].append(result)
        if result.solved and result.solve_step is not None:
            solve_steps.append(result.solve_step)

    for captcha_type, results in grouped.items():
        solved_count = sum(1 for r in results if r.solved)
        solve_steps_for_type = [
            r.solve_step for r in results if r.solved and r.solve_step is not None
        ]
        results_by_type[captcha_type] = {
            "individual_results": [r.solved for r in results],
            "solved_count": solved_count,
            "total_count": len(results),
            "success_rate": (solved_count / len(results)) * 100 if results else 0,
            "average_solve_steps": (
                sum(solve_steps_for_type) / len(solve_steps_for_type)
                if solve_steps_for_type
                else None
            ),
        }
        overall_solved += solved_count

    summary = {
        "overall_stats": {
            "total_captchas": overall_total,
            "total_solved": overall_solved,
            "overall_success_rate": (overall_solved / overall_total) * 100 if overall_total else 0,
            "average_solve_steps": (
                sum(solve_steps) / len(solve_steps) if solve_steps else None
            ),
        },
        "by_type": results_by_type,
        "tasks": [asdict(result) for result in task_results],
    }

    return summary
