#!/usr/bin/env python3
"""Parser for <tool_call> formatted outputs."""

from __future__ import annotations

import json
from typing import List, Optional

from actions import Action
from utils import get_logger
from parsers.base import ActionParser

logger = get_logger(__name__)


class ToolCallActionParser(ActionParser):
    """Parse tool-call JSON blocks into actions."""

    name = "tool_call"
    coordinate_grid = 1000

    def parse_response(self, response: str) -> List[Action]:
        actions: List[Action] = []
        for json_str in self._extract_tool_calls(response):
            actions.extend(self._parse_tool_call(json_str))

        logger.debug("Parsed %s actions from tool-call response", len(actions))
        return actions

    def _extract_tool_calls(self, response: str) -> List[str]:
        calls: List[str] = []
        inside = False
        buffer: List[str] = []

        for raw_line in response.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            if "<tool_call>" in line:
                if "</tool_call>" in line:
                    start = line.find("<tool_call>") + len("<tool_call>")
                    end = line.find("</tool_call>")
                    payload = line[start:end].strip()
                    if payload:
                        calls.append(payload)
                    continue
                inside = True
                buffer = []
                continue

            if line.startswith("</tool_call>"):
                inside = False
                if buffer:
                    calls.append("\n".join(buffer))
                    buffer = []
                continue

            if inside:
                buffer.append(line)
                continue

            if line.startswith("{") and line.endswith("}"):
                calls.append(line)

        if buffer:
            calls.append("\n".join(buffer))

        return calls

    def _parse_tool_call(self, json_str: str) -> List[Action]:
        actions: List[Action] = []

        for payload in self._extract_payloads(json_str):
            description = json.dumps(payload, ensure_ascii=True)
            parsed = self._actions_from_payload(payload, description)
            if parsed:
                actions.extend(parsed)

        return actions

    def _extract_payloads(self, json_str: str) -> List[dict]:
        stripped = json_str.strip()
        if not stripped:
            return []

        direct = self._load_json_payloads(stripped)
        if direct is not None:
            return direct

        trimmed = stripped.rstrip(", \t\r\n")
        comma_separated = self._load_json_payloads(f"[{trimmed}]")
        if comma_separated is not None:
            return comma_separated

        payloads = self._extract_fragments(stripped)
        if not payloads:
            logger.debug("Failed to parse tool call payloads from response fragment")
        return payloads

    def _load_json_payloads(self, candidate: str) -> Optional[List[dict]]:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return None

        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        if isinstance(parsed, dict):
            return [parsed]
        return []

    def _extract_fragments(self, stripped: str) -> List[dict]:
        decoder = json.JSONDecoder()
        payloads: List[dict] = []
        idx = 0
        length = len(stripped)

        while idx < length:
            while idx < length and stripped[idx] not in "{[":
                idx += 1
            if idx >= length:
                break
            try:
                parsed, end = decoder.raw_decode(stripped, idx)
            except json.JSONDecodeError:
                idx += 1
                continue
            if isinstance(parsed, list):
                payloads.extend([item for item in parsed if isinstance(item, dict)])
            elif isinstance(parsed, dict):
                payloads.append(parsed)
            idx = end
            while idx < length and stripped[idx] in " \t\r\n,":
                idx += 1

        return payloads

    def _actions_from_payload(self, payload: dict, description: str) -> List[Action]:
        if payload.get("name") != "computer_use":
            return []

        args = payload.get("arguments") or {}
        action_name = args.get("action")
        if not action_name:
            return []

        coord = args.get("coordinate")
        x = y = None
        if isinstance(coord, (list, tuple)) and len(coord) >= 2:
            x, y = coord[0], coord[1]

        if action_name == "left_click":
            return [Action(type="click", x=x, y=y, coord_mode="grid", description=description)]
        if action_name == "right_click":
            return [Action(type="right_click", x=x, y=y, coord_mode="grid", description=description)]
        if action_name == "middle_click":
            return [Action(type="middle_click", x=x, y=y, coord_mode="grid", description=description)]
        if action_name == "double_click":
            return [Action(type="double_click", x=x, y=y, coord_mode="grid", description=description)]
        if action_name == "mouse_move":
            return [Action(type="mouse_move", x=x, y=y, coord_mode="grid", description=description)]
        if action_name == "left_click_drag":
            return [
                Action(
                    type="drag_to",
                    x=x,
                    y=y,
                    coord_mode="grid",
                    duration=args.get("duration"),
                    description=description,
                )
            ]
        if action_name == "type":
            return [Action(type="type", text=args.get("text", ""), description=description)]
        if action_name == "key":
            keys = args.get("keys")
            if isinstance(keys, list):
                keys = [str(key) for key in keys]
            elif isinstance(keys, str):
                keys = keys.replace("+", " ").split()
            else:
                keys = None
            return [Action(type="key", keys=keys, description=description)]
        if action_name == "scroll":
            return [
                Action(
                    type="scroll",
                    x=x,
                    y=y,
                    coord_mode="grid",
                    pixels=args.get("pixels"),
                    description=description,
                )
            ]
        if action_name == "wait":
            return [Action(type="wait", duration=args.get("time", 5.0), description=description)]
        if action_name in {"terminate", "answer"}:
            return [Action(type="terminate", description=description)]

        return []
