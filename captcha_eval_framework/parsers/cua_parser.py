#!/usr/bin/env python3
"""Parser for OpenAI CUA computer_call outputs."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from actions import Action
from utils import get_logger
from parsers.base import ActionParser

logger = get_logger(__name__)


class ComputerCallActionParser(ActionParser):
    """Parse computer_call response items into actions."""

    name = "computer_call"

    def parse_response(self, response: str) -> List[Action]:
        items = self._extract_items(response)
        if not items:
            return []

        actions: List[Action] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "computer_call":
                continue
            action = item.get("action")
            if not isinstance(action, dict):
                continue
            description = json.dumps(item, ensure_ascii=True)
            actions.extend(self._actions_from_action(action, description))

        logger.debug("Parsed %s actions from computer-call response", len(actions))
        return actions

    def _extract_items(self, response: str) -> List[Dict[str, Any]]:
        response = (response or "").strip()
        if not response:
            return []
        try:
            payload = json.loads(response)
        except json.JSONDecodeError:
            return []

        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]

        if isinstance(payload, dict):
            if isinstance(payload.get("output"), list):
                return [item for item in payload["output"] if isinstance(item, dict)]
            if payload.get("type") == "computer_call":
                return [payload]
            data = payload.get("data")
            if isinstance(data, dict) and isinstance(data.get("output"), list):
                return [item for item in data["output"] if isinstance(item, dict)]

        return []

    def _actions_from_action(self, action: Dict[str, Any], description: str) -> List[Action]:
        action_type = action.get("type")
        if not action_type:
            return []

        action_type = str(action_type)
        coord_mode = "absolute"

        if action_type == "click":
            button = str(action.get("button", "left")).lower()
            click_type = "click"
            if button == "right":
                click_type = "right_click"
            elif button == "middle":
                click_type = "middle_click"
            return [
                Action(
                    type=click_type,
                    x=self._as_number(action.get("x")),
                    y=self._as_number(action.get("y")),
                    coord_mode=coord_mode,
                    description=description,
                )
            ]

        if action_type == "double_click":
            return [
                Action(
                    type="double_click",
                    x=self._as_number(action.get("x")),
                    y=self._as_number(action.get("y")),
                    coord_mode=coord_mode,
                    description=description,
                )
            ]

        if action_type in {"mouse_move", "move"}:
            return [
                Action(
                    type="mouse_move",
                    x=self._as_number(action.get("x")),
                    y=self._as_number(action.get("y")),
                    coord_mode=coord_mode,
                    description=description,
                )
            ]

        if action_type == "scroll":
            x = self._as_number(action.get("x"))
            y = self._as_number(action.get("y"))
            scroll_x = self._as_number(action.get("scroll_x"))
            scroll_y = self._as_number(action.get("scroll_y"))
            pixels = self._as_number(action.get("pixels"))
            if scroll_y is None and scroll_x is None and pixels is not None:
                scroll_y = pixels

            if scroll_y is not None and (
                scroll_x is None or abs(scroll_y) >= abs(scroll_x)
            ):
                return [
                    Action(
                        type="scroll",
                        x=x,
                        y=y,
                        pixels=scroll_y,
                        coord_mode=coord_mode,
                        description=description,
                    )
                ]
            if scroll_x is not None:
                direction = "right" if scroll_x > 0 else "left"
                return [
                    Action(
                        type="scroll",
                        x=x,
                        y=y,
                        text=direction,
                        coord_mode=coord_mode,
                        description=description,
                    )
                ]
            return [
                Action(
                    type="scroll",
                    x=x,
                    y=y,
                    coord_mode=coord_mode,
                    description=description,
                )
            ]

        if action_type == "keypress":
            keys = action.get("keys")
            if isinstance(keys, str):
                keys = [keys]
            if isinstance(keys, list):
                keys = [str(key) for key in keys]
            else:
                keys = None
            return [Action(type="key", keys=keys, description=description)]

        if action_type == "type":
            return [Action(type="type", text=str(action.get("text", "")), description=description)]

        if action_type == "wait":
            duration = self._as_number(
                action.get("duration", action.get("time", action.get("seconds")))
            )
            if duration is None:
                duration = 2.0
            return [Action(type="wait", duration=duration, description=description)]

        if action_type == "screenshot":
            return [Action(type="wait", duration=0.5, description=description)]

        if action_type in {"drag", "drag_to"}:
            start_x, start_y, end_x, end_y = self._extract_drag_points(action)
            if None not in (start_x, start_y, end_x, end_y):
                return [
                    Action(
                        type="drag",
                        x=start_x,
                        y=start_y,
                        end_x=end_x,
                        end_y=end_y,
                        coord_mode=coord_mode,
                        description=description,
                    )
                ]
            end_x = self._as_number(action.get("x"))
            end_y = self._as_number(action.get("y"))
            if end_x is not None and end_y is not None:
                return [
                    Action(
                        type="drag_to",
                        x=end_x,
                        y=end_y,
                        coord_mode=coord_mode,
                        duration=self._as_number(action.get("duration")),
                        description=description,
                    )
                ]

        if action_type in {"terminate", "answer"}:
            return [Action(type="terminate", description=description)]

        return []

    def _extract_drag_points(
        self, action: Dict[str, Any]
    ) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        start = action.get("start")
        end = action.get("end")
        if isinstance(start, dict) and isinstance(end, dict):
            return (
                self._as_number(start.get("x")),
                self._as_number(start.get("y")),
                self._as_number(end.get("x")),
                self._as_number(end.get("y")),
            )

        return (
            self._as_number(action.get("start_x")),
            self._as_number(action.get("start_y")),
            self._as_number(action.get("end_x")),
            self._as_number(action.get("end_y")),
        )

    def _as_number(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
