#!/usr/bin/env python3
"""Playwright action executor for the CAPTCHA evaluation framework."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from playwright.async_api import Page

from actions import Action
from utils import ACTION_DELAY_MS, get_logger

logger = get_logger(__name__)


class ActionExecutor:
    """Executes parsed actions on web pages using Playwright."""
    _MODIFIER_KEYS = {"Control", "Shift", "Alt", "Meta"}

    def __init__(self) -> None:
        self._last_mouse_pos: Optional[Tuple[int, int]] = None

    async def execute_actions(
        self,
        page: Page,
        actions: List[Action],
        region: Optional[Dict[str, int]],
    ) -> bool:
        try:
            for action in actions:
                action_type = action.type

                if action_type == "click":
                    x, y = self._resolve_position(action.x, action.y, region)
                    await page.mouse.click(x, y)
                    self._last_mouse_pos = (x, y)

                elif action_type == "drag":
                    start_x, start_y = self._resolve_position(action.x, action.y, region)
                    end_x, end_y = self._resolve_position(action.end_x, action.end_y, region)
                    await page.mouse.move(start_x, start_y)
                    await page.mouse.down()
                    await page.mouse.move(end_x, end_y)
                    await page.mouse.up()
                    self._last_mouse_pos = (end_x, end_y)

                elif action_type == "drag_to":
                    end_x, end_y = self._resolve_position(action.x, action.y, region)
                    start = self._last_mouse_pos
                    if not start:
                        start = self._fallback_start(region, end_x, end_y)
                        logger.debug("Missing drag start position; using fallback %s", start)
                    await page.mouse.move(start[0], start[1])
                    await page.mouse.down()
                    await page.mouse.move(end_x, end_y)
                    await page.mouse.up()
                    self._last_mouse_pos = (end_x, end_y)

                elif action_type == "type":
                    await self._execute_type_action(page, action, region)

                elif action_type == "type_at":
                    await self._execute_type_at_action(page, action, region)

                elif action_type in {"left_double", "double_click"}:
                    x, y = self._resolve_position(action.x, action.y, region)
                    await page.mouse.dblclick(x, y)
                    self._last_mouse_pos = (x, y)

                elif action_type in {"right_single", "right_click"}:
                    x, y = self._resolve_position(action.x, action.y, region)
                    await page.mouse.click(x, y, button="right")
                    self._last_mouse_pos = (x, y)

                elif action_type == "middle_click":
                    x, y = self._resolve_position(action.x, action.y, region)
                    await page.mouse.click(x, y, button="middle")
                    self._last_mouse_pos = (x, y)

                elif action_type == "scroll":
                    await self._execute_scroll_action(page, action, region)

                elif action_type == "hotkey":
                    await self._execute_hotkey_action(page, action.text)

                elif action_type == "key":
                    await self._execute_key_action(page, action.keys)

                elif action_type == "mouse_move":
                    x, y = self._resolve_position(action.x, action.y, region)
                    await page.mouse.move(x, y)
                    self._last_mouse_pos = (x, y)

                elif action_type == "wait":
                    duration = action.duration or 5.0
                    await page.wait_for_timeout(int(duration * 1000))

                elif action_type in {"finished", "terminate"}:
                    continue

                await page.wait_for_timeout(ACTION_DELAY_MS)

            return True
        except Exception as exc:
            logger.error("Error executing actions: %s", exc)
            return False

    def _resolve_position(
        self,
        x: Optional[float],
        y: Optional[float],
        region: Optional[Dict[str, int]],
    ) -> Tuple[int, int]:
        if x is None or y is None:
            raise ValueError("Action missing coordinates")

        offset_x = region.get("x", 0) if region else 0
        offset_y = region.get("y", 0) if region else 0
        return offset_x + int(x), offset_y + int(y)

    def _fallback_start(
        self,
        region: Optional[Dict[str, int]],
        end_x: int,
        end_y: int,
    ) -> Tuple[int, int]:
        if not region:
            return (end_x, end_y)
        center_x = region.get("x", 0) + region.get("width", 0) // 2
        center_y = region.get("y", 0) + region.get("height", 0) // 2
        return (center_x, center_y)

    async def _execute_type_action(self, page: Page, action: Action, region: Optional[Dict[str, int]]) -> None:
        text = action.text or ""
        input_selectors = [
            'input[type="text"]',
            'input[type="password"]',
            'input:not([type])',
            "textarea",
            'input[id*="captcha"]',
            'input[name*="captcha"]',
            'input[placeholder*="captcha"]',
            'input[class*="captcha"]',
            'input[id*="text"]',
            'input[name*="text"]',
            'input[placeholder*="text"]',
            'input[class*="text"]',
            'input[id*="answer"]',
            'input[name*="answer"]',
            'input[placeholder*="answer"]',
            'input[class*="answer"]',
        ]

        region_bounds = None
        if region:
            region_bounds = (
                region.get("x", 0),
                region.get("y", 0),
                region.get("x", 0) + region.get("width", 0),
                region.get("y", 0) + region.get("height", 0),
            )

        combined_selector = ",".join(input_selectors)
        input_found = False
        try:
            elements = await page.query_selector_all(combined_selector)
            for element in elements:
                box = await element.bounding_box()
                if not box:
                    continue
                if region_bounds:
                    if not (
                        region_bounds[0] <= box["x"] <= region_bounds[2]
                        and region_bounds[1] <= box["y"] <= region_bounds[3]
                    ):
                        continue
                await element.fill(text)
                input_found = True
                break
        except Exception:
            input_found = False

        if not input_found:
            try:
                element = await page.query_selector(combined_selector)
                if element:
                    await element.click()
                    await element.fill(text)
                    input_found = True
            except Exception:
                input_found = False

        if not input_found:
            logger.debug("No target input field found; using global typing")
            await page.keyboard.type(text)

    async def _execute_type_at_action(self, page: Page, action: Action, region: Optional[Dict[str, int]]) -> None:
        text = action.text or ""
        x, y = self._resolve_position(action.x, action.y, region)
        await page.mouse.click(x, y)
        await page.wait_for_timeout(100)
        await page.keyboard.type(text)
        self._last_mouse_pos = (x, y)

    async def _execute_scroll_action(self, page: Page, action: Action, region: Optional[Dict[str, int]]) -> None:
        pixels = action.pixels
        if pixels is not None:
            await page.mouse.wheel(0, int(pixels))
            return

        direction = (action.text or "down").lower()
        wheel_delta = 1 if direction in {"down", "right"} else -1

        if direction in {"left", "right"}:
            await page.mouse.wheel(wheel_delta, 0)
        else:
            await page.mouse.wheel(0, wheel_delta)

    async def _execute_hotkey_action(self, page: Page, key_combo: Optional[str]) -> None:
        if not key_combo:
            return
        keys = self._parse_key_combo(key_combo)
        await self._execute_key_action(page, keys)

    async def _execute_key_action(self, page: Page, keys: Optional[List[str]]) -> None:
        if not keys:
            return

        normalized = [self._normalize_key(key) for key in keys if key]
        if not normalized:
            return

        modifiers: List[str] = []
        main_keys: List[str] = []
        for key in normalized:
            if key in self._MODIFIER_KEYS:
                if key not in modifiers:
                    modifiers.append(key)
            else:
                main_keys.append(key)

        if not modifiers:
            if len(main_keys) == 1:
                await page.keyboard.press(main_keys[0])
            else:
                for key in main_keys:
                    await page.keyboard.press(key)
            return

        try:
            for modifier in modifiers:
                await page.keyboard.down(modifier)

            if not main_keys:
                await page.keyboard.press(modifiers[-1])
            elif len(main_keys) == 1:
                await page.keyboard.press(main_keys[0])
            else:
                for key in main_keys:
                    await page.keyboard.press(key)
        finally:
            for modifier in reversed(modifiers):
                await page.keyboard.up(modifier)

    def _parse_key_combo(self, key_combo: str) -> List[str]:
        cleaned = key_combo.strip()
        if not cleaned:
            return []
        cleaned = cleaned.strip("[](){}")
        cleaned = cleaned.replace('"', " ").replace("'", " ")
        return [token for token in re.split(r"[+\-,\s]+", cleaned) if token]

    def _normalize_key(self, key: str) -> str:
        key_lower = key.lower()
        mapping = {
            "ctrl": "Control",
            "control": "Control",
            "shift": "Shift",
            "alt": "Alt",
            "option": "Alt",
            "meta": "Meta",
            "cmd": "Meta",
            "command": "Meta",
            "enter": "Enter",
            "return": "Enter",
            "esc": "Escape",
            "escape": "Escape",
            "tab": "Tab",
            "space": "Space",
            "backspace": "Backspace",
            "delete": "Delete",
            "del": "Delete",
            "up": "ArrowUp",
            "down": "ArrowDown",
            "left": "ArrowLeft",
            "right": "ArrowRight",
            "arrowup": "ArrowUp",
            "arrowdown": "ArrowDown",
            "arrowleft": "ArrowLeft",
            "arrowright": "ArrowRight",
            "pgup": "PageUp",
            "pgdn": "PageDown",
        }
        return mapping.get(key_lower, key)
