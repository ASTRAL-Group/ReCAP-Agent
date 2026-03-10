#!/usr/bin/env python3
"""Shared configuration and logging helpers for trace generation."""

from __future__ import annotations

import logging
import os
from typing import Optional

# Actor model configuration (used for action generation in self-correction mode).
ACTOR_API_KEY = os.getenv("ACTOR_API_KEY", "").strip()
ACTOR_MODEL = os.getenv("ACTOR_MODEL", "Qwen/Qwen3-VL-8B-Instruct")
ACTOR_BASE_URL = os.getenv("ACTOR_BASE_URL", "http://localhost:8000/v1")
ACTOR_MAX_COMPLETION_TOKENS = int(os.getenv("ACTOR_MAX_COMPLETION_TOKENS", "1024"))
ACTOR_TEMPERATURE = float(os.getenv("ACTOR_TEMPERATURE", "0.7"))
ACTOR_TOP_P = float(os.getenv("ACTOR_TOP_P", "0.8"))

# Reasoning model configuration (used for reasoning traces in direct/correction modes).
REASONER_API_KEY = os.getenv("REASONER_API_KEY", "").strip()
REASONER_MODEL = os.getenv("REASONER_MODEL", "gpt-5.2")
REASONER_BASE_URL = os.getenv("REASONER_BASE_URL", "https://api.openai.com/v1")
REASONER_MAX_OUTPUT_TOKENS = int(os.getenv("REASONER_MAX_OUTPUT_TOKENS", "1000"))
REASONER_MAX_ATTEMPTS = int(os.getenv("REASONER_MAX_ATTEMPTS", "2"))

# Common viewport sizes for sample diversity
COMMON_VIEWPORTS = [
    {"width": 1200, "height": 900},
    {"width": 1280, "height": 800},
    {"width": 1366, "height": 768},
    {"width": 1280, "height": 720},
]

RUNS_DIR = os.getenv("RUNS_DIR", "runs")
LOG_LEVEL = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)

_logging_configured = False
_file_handler: Optional[logging.Handler] = None


def setup_logging(run_timestamp: Optional[str] = None, log_file_path: Optional[str] = None) -> None:
    """Set up centralized logging configuration."""
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
            log_file = f"{RUNS_DIR}/{run_timestamp}/trace-generation.log"
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
    return logging.getLogger(name)
