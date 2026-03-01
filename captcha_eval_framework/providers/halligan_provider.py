#!/usr/bin/env python3
"""Provider adapter for Halligan CAPTCHAs."""

from __future__ import annotations

import os
import random
from typing import Dict, List, Optional

from PIL import Image
from io import BytesIO

from actions import CaptchaTask
from providers.base import CaptchaProvider
from utils import HALLIGAN_RESPONSE_TIMEOUT, HALLIGAN_PROVIDER_URL

CAPTCHA_TYPES: Dict[str, Dict[str, int]] = {
    "lemin": {"x": 0, "y": 0, "width": 1200, "height": 900},
    "geetest/slide": {"x": 0, "y": 0, "width": 1200, "height": 900},
    "geetest/gobang": {"x": 0, "y": 0, "width": 1200, "height": 900},
    "geetest/icon": {"x": 0, "y": 0, "width": 1200, "height": 900},
    "geetest/iconcrush": {"x": 0, "y": 0, "width": 1200, "height": 900},
    "baidu": {"x": 0, "y": 0, "width": 1200, "height": 900},
    "hcaptcha": {"x": 0, "y": 0, "width": 1200, "height": 900},
    "botdetect": {"x": 0, "y": 0, "width": 1200, "height": 900},
    "arkose/multichoice/square_icon": {"x": 0, "y": 0, "width": 1200, "height": 900},
    "arkose/multichoice/galaxies": {"x": 0, "y": 0, "width": 1200, "height": 900},
    "arkose/multichoice/dice_pair": {"x": 0, "y": 0, "width": 1200, "height": 900},
    "arkose/multichoice/hand_number": {"x": 0, "y": 0, "width": 1200, "height": 900},
    "arkose/multichoice/card": {"x": 0, "y": 0, "width": 1200, "height": 900},
    "arkose/multichoice/counting": {"x": 0, "y": 0, "width": 1200, "height": 900},
    "arkose/multichoice/rotated": {"x": 0, "y": 0, "width": 1200, "height": 900},
    "arkose/paged/dice_match": {"x": 0, "y": 0, "width": 1200, "height": 900},
    "arkose/paged/rockstack": {"x": 0, "y": 0, "width": 1200, "height": 900},
    "arkose/paged/numbermatch": {"x": 0, "y": 0, "width": 1200, "height": 900},
    "arkose/paged/orbit_match_game": {"x": 0, "y": 0, "width": 1200, "height": 900},
    "arkose/paged/3d_rollball_objects": {"x": 0, "y": 0, "width": 1200, "height": 900},
    "mtcaptcha": {"x": 0, "y": 0, "width": 1200, "height": 900},
    "recaptchav2": {"x": 0, "y": 0, "width": 1200, "height": 900},
    "tencent": {"x": 0, "y": 0, "width": 1200, "height": 900},
    "yandex/text": {"x": 0, "y": 0, "width": 1200, "height": 900},
    "yandex/kaleidoscope": {"x": 0, "y": 0, "width": 1200, "height": 900},
    "amazon": {"x": 0, "y": 0, "width": 1200, "height": 900},
}

BENCHMARK_SAMPLE_IDS = list(range(1, 101))

HALLIGAN_PREPARE_DELAYS = {
    "recaptchav2": int(os.getenv("HALLIGAN_PREPARE_DELAY_RECAPTCHAV2", "2000")),
    "hcaptcha": int(os.getenv("HALLIGAN_PREPARE_DELAY_HCAPTCHA", "2000")),
    "arkose": int(os.getenv("HALLIGAN_PREPARE_DELAY_ARKOSE", "1000")),
    "mtcaptcha": int(os.getenv("HALLIGAN_PREPARE_DELAY_MTCAPTCHA", "2000")),
}


class HalliganProvider(CaptchaProvider):
    """Adapter for the static benchmark server."""

    name = "halligan"
    expects_submit_response = True

    def __init__(self, benchmark_url: str = HALLIGAN_PROVIDER_URL) -> None:
        self.benchmark_url = benchmark_url

    def build_tasks(
        self,
        test_mode: str,
        test_size: Optional[int],
        seed: Optional[int],
        captcha_name: Optional[str],
    ) -> List[CaptchaTask]:
        if test_mode == "once":
            rng = random.Random(seed if seed is not None else 0)
            return [
                CaptchaTask(
                    self.name,
                    captcha_type,
                    sample_id=rng.choice(BENCHMARK_SAMPLE_IDS),
                    region=None,
                )
                for captcha_type in CAPTCHA_TYPES
            ]

        if test_mode == "complete":
            return self._complete_baseline_tasks()

        if test_mode == "custom":
            if not test_size or test_size < 1:
                raise ValueError("custom mode requires --test-size >= 1")
            if captcha_name:
                if captcha_name not in CAPTCHA_TYPES:
                    raise ValueError(f"Invalid captcha name: {captcha_name}")
                named_pool = [
                    CaptchaTask(self.name, captcha_name, sample_id=sample_id, region=None)
                    for sample_id in BENCHMARK_SAMPLE_IDS
                ]
                return self._round_robin_pick(named_pool, test_size, seed)
            return self._round_robin_pick(self._complete_baseline_tasks(), test_size, seed)

        raise ValueError(f"Invalid test mode: {test_mode}")

    async def open_task(self, page, task: CaptchaTask) -> None:
        if task.sample_id is None:
            raise ValueError("Benchmark tasks require sample_id")
        url = f"{self.benchmark_url}/{task.captcha_type}/{task.sample_id}"
        await page.goto(url)

    async def prepare_task(self, page, task: CaptchaTask) -> None:
        delay = HALLIGAN_PREPARE_DELAYS.get(task.captcha_type, 1000)

        if "recaptchav2" in task.captcha_type:
            checkbox = page.frame_locator("#checkbox")
            await checkbox.locator("#recaptcha-anchor").click()
            await page.wait_for_timeout(delay)
        elif "hcaptcha" in task.captcha_type:
            checkbox = page.frame_locator("#checkbox")
            await checkbox.locator("#anchor").click()
            await page.wait_for_timeout(delay)
        elif "arkose" in task.captcha_type:
            frame = page.frame_locator("#funcaptcha")
            await frame.locator(".start-button").click()
        elif "mtcaptcha" in task.captcha_type:
            await page.wait_for_timeout(delay)

    async def capture_task(self, page, task: CaptchaTask):
        region = task.region
        if region:
            clip = {
                "x": region["x"],
                "y": region["y"],
                "width": region["width"],
                "height": region["height"],
            }
            screenshot = await page.screenshot(clip=clip)
        else:
            screenshot = await page.screenshot()

        image = Image.open(BytesIO(screenshot))
        return image, image.size[0], image.size[1]

    async def check_solved(self, page, task: CaptchaTask) -> Optional[bool]:
        try:
            response = await page.wait_for_response(
                lambda r: "/submit" in r.url,
                timeout=HALLIGAN_RESPONSE_TIMEOUT,
            )
            data = await response.json()
            return bool(data.get("solved", False))
        except Exception:
            return None

    async def capture_final(self, page, task: CaptchaTask, path: str) -> None:
        if task.region:
            await page.screenshot(path=path, clip=task.region)
        else:
            await page.screenshot(path=path)

    def _complete_baseline_tasks(self) -> List[CaptchaTask]:
        tasks: List[CaptchaTask] = []
        for captcha_type in CAPTCHA_TYPES:
            for sample_id in BENCHMARK_SAMPLE_IDS:
                tasks.append(
                    CaptchaTask(
                        self.name,
                        captcha_type,
                        sample_id=sample_id,
                        region=None,
                    )
                )
        return tasks

    def _round_robin_pick(
        self,
        baseline: List[CaptchaTask],
        count: int,
        seed: Optional[int],
    ) -> List[CaptchaTask]:
        if not baseline:
            return []
        offset = 0 if seed is None else (seed % len(baseline))
        selected: List[CaptchaTask] = []
        for idx in range(count):
            task = baseline[(offset + idx) % len(baseline)]
            selected.append(
                CaptchaTask(
                    provider_name=task.provider_name,
                    captcha_type=task.captcha_type,
                    sample_id=task.sample_id,
                    attempt=idx + 1,
                    region=task.region,
                )
            )
        return selected
