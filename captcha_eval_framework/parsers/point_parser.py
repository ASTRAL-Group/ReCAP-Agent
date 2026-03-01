#!/usr/bin/env python3
"""Parser for <point> and <relative-point> action formats."""

from __future__ import annotations

import re
from typing import List, Optional

from actions import Action
from utils import get_logger
from parsers.base import ActionParser

logger = get_logger(__name__)


class PointActionParser(ActionParser):
    """Parser for UI-TARS point and relative-point formats."""

    name = "point"

    def __init__(self) -> None:
        number_pattern = r"\d+(?:\.\d+)?"
        point_pair = rf"({number_pattern})\s+({number_pattern})"
        absolute_point = rf"<point>{point_pair}</point>"
        relative_point = rf"<relative-point>{point_pair}</relative-point>"
        box_pair = rf"\(({number_pattern}),\s*({number_pattern})\)"
        boxed_with_markers = rf"<\|box_start\|>{box_pair}<\|box_end\|>"

        self.action_patterns = {
            "click": [
                {"pattern": rf"click\(point='{absolute_point}'\)", "action_type": "click", "coord_mode": "absolute"},
                {"pattern": rf"click\(point='{relative_point}'\)", "action_type": "click", "coord_mode": "relative"},
                {"pattern": rf"left_double\(point='{absolute_point}'\)", "action_type": "left_double", "coord_mode": "absolute"},
                {"pattern": rf"left_double\(point='{relative_point}'\)", "action_type": "left_double", "coord_mode": "relative"},
                {"pattern": rf"right_single\(point='{absolute_point}'\)", "action_type": "right_single", "coord_mode": "absolute"},
                {"pattern": rf"right_single\(point='{relative_point}'\)", "action_type": "right_single", "coord_mode": "relative"},
                {"pattern": rf"click\(start_box='{boxed_with_markers}'\)", "action_type": "click", "coord_mode": "absolute"},
                {"pattern": rf"left_double\(start_box='{boxed_with_markers}'\)", "action_type": "left_double", "coord_mode": "absolute"},
                {"pattern": rf"right_single\(start_box='{boxed_with_markers}'\)", "action_type": "right_single", "coord_mode": "absolute"},
                {"pattern": rf"click\(start_box=['\"]{box_pair}['\"]\)", "action_type": "click", "coord_mode": "absolute"},
                {"pattern": rf"left_double\(start_box=['\"]{box_pair}['\"]\)", "action_type": "left_double", "coord_mode": "absolute"},
                {"pattern": rf"right_single\(start_box=['\"]{box_pair}['\"]\)", "action_type": "right_single", "coord_mode": "absolute"},
                {"pattern": rf"click\s+(?:at\s+)?\(?({number_pattern}),\s*({number_pattern})\)?", "action_type": "click", "coord_mode": "absolute"},
                {"pattern": rf"tap\s+(?:at\s+)?\(?({number_pattern}),\s*({number_pattern})\)?", "action_type": "click", "coord_mode": "absolute"},
            ],
            "drag": [
                {"pattern": rf"drag\(start_point='{absolute_point}',\s*end_point='{absolute_point}'\)", "coord_mode": "absolute"},
                {"pattern": rf"drag\(start_point='{relative_point}',\s*end_point='{relative_point}'\)", "coord_mode": "relative"},
                {"pattern": rf"drag\(start_box='{boxed_with_markers}',\s*end_box='{boxed_with_markers}'\)", "coord_mode": "absolute"},
                {"pattern": rf"drag\(start_box=['\"]{box_pair}['\"],\s*end_box=['\"]{box_pair}['\"]\)", "coord_mode": "absolute"},
                {"pattern": rf"drag\s+from\s+\(?({number_pattern}),\s*({number_pattern})\)?\s+to\s+\(?({number_pattern}),\s*({number_pattern})\)?", "coord_mode": "absolute"},
                {"pattern": rf"slide\s+from\s+\(?({number_pattern}),\s*({number_pattern})\)?\s+to\s+\(?({number_pattern}),\s*({number_pattern})\)?", "coord_mode": "absolute"},
            ],
            "type": [
                {"pattern": r"type\(content='([^']+)'\)"},
                {"pattern": r"type\(content=\"([^\"]+)\"\)"},
                {"pattern": r"type\s+[\"']([^\"']+)[\"']"},
                {"pattern": r"enter\s+[\"']([^\"']+)[\"']"},
                {"pattern": r"input\s+[\"']([^\"']+)[\"']"},
            ],
            "scroll": [
                {"pattern": rf"scroll\(point='{absolute_point}',\s*direction='(down|up|right|left)'\)", "coord_mode": "absolute"},
                {"pattern": rf"scroll\(point='{relative_point}',\s*direction='(down|up|right|left)'\)", "coord_mode": "relative"},
            ],
            "hotkey": [
                {"pattern": r"hotkey\(key='([^']+)'\)"},
            ],
            "wait": [
                {"pattern": r"wait\(\)"},
                {"pattern": r"wait\s+(\d+(?:\.\d+)?)\s*seconds?"},
            ],
            "finished": [
                {"pattern": r"finished\(content='([^']+)'\)"},
                {"pattern": r"finished\(content=\"([^\"]+)\"\)"},
                {"pattern": r"finished\(\)"},
                {"pattern": r"finished\s*\(\s*\)"},
            ],
        }

    def parse_response(self, response: str) -> List[Action]:
        actions: List[Action] = []
        segments = self._extract_action_segments(response)

        for line_num, segment in enumerate(segments, 1):
            action = self._parse_line(segment, line_num)
            if action:
                actions.append(action)

        logger.debug("Parsed %s actions from point response", len(actions))
        return actions

    def _extract_action_segments(self, response: str) -> List[str]:
        segments: List[str] = []
        for raw_line in response.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("```"):
                continue
            if re.match(r"^thought\b", line, re.IGNORECASE):
                continue

            line = re.sub(r"^[\-\*]\s*", "", line)
            line = re.sub(r"^\d+[\.)]\s*", "", line)
            label_match = re.match(
                r"^(?:actions?|action\s*\d+|step\s*\d+)\s*[:\-]\s*(.*)$",
                line,
                flags=re.IGNORECASE,
            )
            if label_match:
                line = label_match.group(1).strip()

            if not line:
                continue

            segments.extend(self._split_into_actions(line))

        return segments

    def _split_into_actions(self, text: str) -> List[str]:
        text = text.strip().strip("`")
        if not text:
            return []

        action_keyword_pattern = re.compile(
            r"(click|left_double|right_single|drag|type|scroll|hotkey|wait|finished)\s*\(",
            re.IGNORECASE,
        )
        matches = list(action_keyword_pattern.finditer(text))

        if not matches:
            return [text]

        segments: List[str] = []
        for idx, match in enumerate(matches):
            start = match.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            segment = text[start:end].strip().strip(";").strip(",")
            if segment:
                segments.append(segment)

        return segments

    def _parse_line(self, line: str, line_num: int) -> Optional[Action]:
        _ = line_num
        original_line = line.strip()
        if not original_line:
            return None

        cleaned_line = re.sub(
            r"^(?:actions?|action\s*\d+|step\s*\d+)\s*[:\-]\s*",
            "",
            original_line,
            flags=re.IGNORECASE,
        )
        cleaned_line = re.sub(r"^[\-\*]\s*", "", cleaned_line)
        cleaned_line = re.sub(r"^\d+[\.)]\s*", "", cleaned_line)
        cleaned_line = cleaned_line.strip()
        if not cleaned_line:
            return None

        line_lower = cleaned_line.lower()

        for pattern_info in self.action_patterns["click"]:
            match = re.search(pattern_info["pattern"], line_lower)
            if match:
                groups = match.groups()
                if len(groups) < 2:
                    continue
                x, y = map(float, groups[:2])
                return Action(
                    type=pattern_info.get("action_type", "click"),
                    x=x,
                    y=y,
                    coord_mode=pattern_info.get("coord_mode", "absolute"),
                    description=original_line,
                )

        for pattern_info in self.action_patterns["drag"]:
            match = re.search(pattern_info["pattern"], line_lower)
            if match:
                groups = match.groups()
                if len(groups) < 4:
                    continue
                start_x, start_y, end_x, end_y = map(float, groups[:4])
                return Action(
                    type="drag",
                    x=start_x,
                    y=start_y,
                    end_x=end_x,
                    end_y=end_y,
                    coord_mode=pattern_info.get("coord_mode", "absolute"),
                    description=original_line,
                )

        for pattern_info in self.action_patterns["type"]:
            match = re.search(pattern_info["pattern"], line_lower)
            if match:
                return Action(type="type", text=match.group(1), description=original_line)

        type_coord_pattern = (
            r"type\s+[\"']?([^\"']+)[\"']?\s+(?:at\s+)?\(?"
            r"(\d+(?:\.\d+)?),\s*(\d+(?:\.\d+)?)\)?"
        )
        match = re.search(type_coord_pattern, line_lower)
        if match:
            text, x, y = match.groups()
            return Action(type="type_at", text=text, x=float(x), y=float(y), description=original_line)

        for pattern_info in self.action_patterns["scroll"]:
            match = re.search(pattern_info["pattern"], line_lower)
            if match:
                groups = match.groups()
                if len(groups) < 3:
                    continue
                x_str, y_str, direction = groups[:3]
                return Action(
                    type="scroll",
                    x=float(x_str),
                    y=float(y_str),
                    text=direction,
                    coord_mode=pattern_info.get("coord_mode", "absolute"),
                    description=original_line,
                )

        for pattern_info in self.action_patterns["hotkey"]:
            match = re.search(pattern_info["pattern"], line_lower)
            if match:
                return Action(type="hotkey", text=match.group(1), description=original_line)

        for pattern_info in self.action_patterns["wait"]:
            match = re.search(pattern_info["pattern"], line_lower)
            if match:
                duration = 5.0 if pattern_info["pattern"] == r"wait\(\)" else float(match.group(1))
                return Action(type="wait", duration=duration, description=original_line)

        for pattern_info in self.action_patterns["finished"]:
            match = re.search(pattern_info["pattern"], line_lower)
            if match:
                text = match.group(1) if match.groups() else ""
                return Action(type="finished", text=text, description=original_line)

        return None
