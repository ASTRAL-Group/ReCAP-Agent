#!/usr/bin/env python3
"""Action and task data structures for the CAPTCHA evaluation framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Action:
    """Represents a single action to execute on the page."""
    type: str
    x: Optional[float] = None
    y: Optional[float] = None
    end_x: Optional[float] = None
    end_y: Optional[float] = None
    text: Optional[str] = None
    keys: Optional[List[str]] = None
    pixels: Optional[float] = None
    duration: Optional[float] = None
    description: str = ""
    coord_mode: str = "relative"


@dataclass
class CaptchaTask:
    """Defines a single CAPTCHA task to run."""
    provider_name: str
    captcha_type: str
    sample_id: Optional[int] = None
    attempt: int = 1
    region: Optional[Dict[str, int]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResult:
    """Captures the outcome of a CAPTCHA task."""
    task_id: str
    provider_name: str
    requested_type: str
    resolved_type: str
    sample_id: Optional[int]
    attempt: int
    solved: bool
    calls_made: int
    finished_flag: bool
    solve_step: Optional[int] = None
    error: Optional[str] = None
