#!/usr/bin/env python3
"""Server registry and base classes for the CAPTCHA evaluation framework."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Type

from actions import CaptchaTask


class CaptchaProviderMeta(type):
    """Metaclass registry for CAPTCHA providers."""

    registry: Dict[str, Type["CaptchaProvider"]] = {}

    def __new__(mcls, name, bases, attrs):
        cls = super().__new__(mcls, name, bases, attrs)
        provider_name = attrs.get("name")
        if provider_name:
            mcls.registry[provider_name] = cls
        return cls


@dataclass
class CaptchaTaskContext:
    """Runtime context for a CAPTCHA task."""
    resolved_type: str
    metadata: Dict[str, str]


class CaptchaProvider(metaclass=CaptchaProviderMeta):
    """Base class for CAPTCHA providers."""

    name: Optional[str] = None
    expects_submit_response: bool = False

    def build_tasks(
        self,
        test_mode: str,
        test_size: Optional[int],
        seed: Optional[int],
        captcha_name: Optional[str],
    ) -> List[CaptchaTask]:
        raise NotImplementedError

    def get_max_calls(self, task: CaptchaTask, default_max_calls: int) -> int:
        return default_max_calls

    async def open_task(self, page, task: CaptchaTask) -> None:
        raise NotImplementedError

    async def prepare_task(self, page, task: CaptchaTask) -> None:
        return None

    async def resolve_task(self, page, task: CaptchaTask) -> CaptchaTaskContext:
        return CaptchaTaskContext(resolved_type=task.captcha_type, metadata={})

    async def capture_task(self, page, task: CaptchaTask):
        raise NotImplementedError

    async def check_solved(self, page, task: CaptchaTask) -> Optional[bool]:
        raise NotImplementedError

    async def capture_final(self, page, task: CaptchaTask, path: str) -> None:
        await page.screenshot(path=path)
