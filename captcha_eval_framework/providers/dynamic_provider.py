#!/usr/bin/env python3
"""Provider adapter for the dynamic CAPTCHAs"""

from __future__ import annotations

import asyncio
import os
from io import BytesIO
from typing import Dict, List, Optional

from PIL import Image

from actions import CaptchaTask
from providers.base import CaptchaProvider, CaptchaTaskContext
from utils import DYNAMIC_PROVIDER_URL, MAX_CALLS

CAPTCHA_TYPES = [
    "text",
    "compact_text",
    "icon_selection",
    "icon_match",
    "slider",
    "image_grid",
    "paged",
]

CHALLENGE_ENDPOINTS = {
    "random": "/challenge/static",
    "text": "/challenge/text",
    "compact_text": "/challenge/compact",
    "icon_selection": "/challenge/icon",
    "icon_match": "/challenge/icon-match",
    "slider": "/challenge/slider",
    "image_grid": "/challenge/image_grid",
    "paged": "/challenge/paged",
}

DYNAMIC_MAX_CALLS = {
    "image_grid": int(os.getenv("DYNAMIC_MAX_CALLS_IMAGE_GRID", "8")),
    "paged": int(os.getenv("DYNAMIC_MAX_CALLS_PAGED", "6")),
    "default": int(os.getenv("DYNAMIC_MAX_CALLS_DEFAULT", str(MAX_CALLS))),
}

class DynamicProvider(CaptchaProvider):
    """Adapter for the dynamic CAPTCHA server."""

    name = "dynamic"

    def __init__(self, server_url: str = DYNAMIC_PROVIDER_URL) -> None:
        self.server_url = server_url
        self._static_reset_done = False
        self._static_reset_lock: Optional[asyncio.Lock] = None

    def build_tasks(
        self,
        test_mode: str,
        test_size: Optional[int],
        seed: Optional[int],
        captcha_name: Optional[str],
    ) -> List[CaptchaTask]:
        _ = seed
        if test_mode == "once":
            return [CaptchaTask(self.name, captcha_type, attempt=1) for captcha_type in CAPTCHA_TYPES]

        if test_mode == "complete":
            return [CaptchaTask(self.name, "random", attempt=attempt) for attempt in range(1, 1001)]

        if test_mode == "custom":
            if not test_size or test_size < 1:
                raise ValueError("custom mode requires --test-size >= 1")
            if captcha_name:
                normalized = captcha_name.lower()
                if normalized not in CAPTCHA_TYPES:
                    raise ValueError(f"Unsupported captcha name: {captcha_name}")
                return [
                    CaptchaTask(self.name, normalized, attempt=attempt)
                    for attempt in range(1, test_size + 1)
                ]
            return [CaptchaTask(self.name, "random", attempt=attempt) for attempt in range(1, test_size + 1)]

        raise ValueError(f"Invalid test mode: {test_mode}")

    def get_max_calls(self, task: CaptchaTask, default_max_calls: int) -> int:
        return DYNAMIC_MAX_CALLS.get(task.captcha_type, DYNAMIC_MAX_CALLS.get("default", default_max_calls))

    async def open_task(self, page, task: CaptchaTask) -> None:
        endpoint = CHALLENGE_ENDPOINTS.get(task.captcha_type)
        if endpoint is None:
            raise ValueError(f"Unsupported CAPTCHA type: {task.captcha_type}")

        if task.captcha_type == "random":
            if self._static_reset_lock is None:
                self._static_reset_lock = asyncio.Lock()
            async with self._static_reset_lock:
                if not self._static_reset_done:
                    endpoint = f"{endpoint}?reset=true"
                    self._static_reset_done = True

        await page.goto(f"{self.server_url}{endpoint}")

    async def resolve_task(self, page, task: CaptchaTask) -> CaptchaTaskContext:
        await page.wait_for_timeout(2000)
        challenge_id = await self._get_challenge_id_from_page(page)
        metadata: Dict[str, str] = {}
        resolved_type = task.captcha_type

        if challenge_id:
            metadata["challenge_id"] = challenge_id
            status = await self._fetch_challenge_status(page, challenge_id)
            resolved_type = status.get("type", task.captcha_type)
            if resolved_type:
                metadata["resolved_type"] = resolved_type
        else:
            metadata["challenge_id"] = ""

        task.metadata.update(metadata)
        return CaptchaTaskContext(resolved_type=resolved_type, metadata=metadata)

    async def capture_task(self, page, task: CaptchaTask):
        screenshot = await page.screenshot()
        image = Image.open(BytesIO(screenshot))
        return image, image.size[0], image.size[1]

    async def check_solved(self, page, task: CaptchaTask) -> Optional[bool]:
        challenge_id = task.metadata.get("challenge_id")
        if not challenge_id:
            return None
        status = await self._fetch_challenge_status(page, challenge_id)
        return bool(status.get("status") == "solved")

    async def _get_challenge_id_from_page(self, page) -> Optional[str]:
        try:
            challenge_id_element = page.locator('input[name="challenge_id"]')
            if await challenge_id_element.count() > 0:
                return await challenge_id_element.get_attribute("value")

            challenge_id_element = page.locator("[data-challenge-id]")
            if await challenge_id_element.count() > 0:
                return await challenge_id_element.get_attribute("data-challenge-id")

            challenge_id = await page.evaluate(
                """
                () => {
                    if (typeof window.challengeId !== 'undefined') {
                        return window.challengeId;
                    }
                    if (typeof window.challenge_id !== 'undefined') {
                        return window.challenge_id;
                    }
                    return null;
                }
                """
            )
            return challenge_id
        except Exception:
            return None

    async def _fetch_challenge_status(self, page, challenge_id: str) -> Dict:
        try:
            status = await page.evaluate(
                f"""
                async () => {{
                    const response = await fetch(`{self.server_url}/status/{challenge_id}`);
                    return response.ok ? await response.json() : {{}};
                }}
                """
            )
            return status or {}
        except Exception:
            return {}
