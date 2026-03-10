"""Trace generation package for CAPTCHA solving."""

from __future__ import annotations

from typing import Any


def record_direct_dataset(*args: Any, **kwargs: Any):
    """Record direct (ground-truth action + reasoning) traces."""
    from .core.recorder import record_conversational_dataset as _impl

    return _impl(*args, **kwargs)


def record_self_correction_dataset(*args: Any, **kwargs: Any):
    """Record failed-attempt self-correction traces."""
    from .core.cli_correction import record_self_correction_dataset as _impl

    return _impl(*args, **kwargs)


__all__ = [
    "record_direct_dataset",
    "record_self_correction_dataset",
]
