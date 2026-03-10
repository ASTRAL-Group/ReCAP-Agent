#!/usr/bin/env python3
"""
Action parser for ui-tars 1.5 model responses.
Converts ui-tars generated instructions into executable actions.
"""

import re
from typing import List, Optional
from dataclasses import dataclass
from .config import get_logger

logger = get_logger(__name__)

@dataclass
class Action:
    """Represents a single action to be executed."""
    type: str  # click, drag, type, wait, etc.
    x: Optional[float] = None
    y: Optional[float] = None
    end_x: Optional[float] = None
    end_y: Optional[float] = None
    text: Optional[str] = None
    duration: Optional[float] = None
    description: str = ""
    coord_mode: str = "absolute"
    end_coord_mode: str = "absolute"

class ActionParser:
    """Parser for ui-tars model responses into executable actions."""
    
    def __init__(self):
        # Updated patterns to match ui-tars model output format
        number_pattern = r"\d+(?:\.\d+)?"
        point_pair = rf"({number_pattern})\s+({number_pattern})"
        absolute_point = rf"<point>{point_pair}</point>"
        relative_point = rf"<relative-point>{point_pair}</relative-point>"
        box_pair = rf"\(({number_pattern}),\s*({number_pattern})\)"
        boxed_with_markers = rf"<\|box_start\|>{box_pair}<\|box_end\|>"

        self.action_patterns = {
            'click': [
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
            'drag': [
                {"pattern": rf"drag\(start_point='{absolute_point}',\s*end_point='{absolute_point}'\)", "coord_mode_start": "absolute", "coord_mode_end": "absolute"},
                {"pattern": rf"drag\(start_point='{relative_point}',\s*end_point='{relative_point}'\)", "coord_mode_start": "relative", "coord_mode_end": "relative"},
                {"pattern": rf"drag\(start_box='{boxed_with_markers}',\s*end_box='{boxed_with_markers}'\)", "coord_mode_start": "absolute", "coord_mode_end": "absolute"},
                {"pattern": rf"drag\(start_box=['\"]{box_pair}['\"],\s*end_box=['\"]{box_pair}['\"]\)", "coord_mode_start": "absolute", "coord_mode_end": "absolute"},
                {"pattern": rf"drag\s+from\s+\(?({number_pattern}),\s*({number_pattern})\)?\s+to\s+\(?({number_pattern}),\s*({number_pattern})\)?", "coord_mode_start": "absolute", "coord_mode_end": "absolute"},
                {"pattern": rf"slide\s+from\s+\(?({number_pattern}),\s*({number_pattern})\)?\s+to\s+\(?({number_pattern}),\s*({number_pattern})\)?", "coord_mode_start": "absolute", "coord_mode_end": "absolute"},
            ],
            'type': [
                {"pattern": r"type\(content='([^']+)'\)"},
                {"pattern": r"type\(content=\"([^\"]+)\"\)"},
                {"pattern": r'type\s+["\']([^"\']+)["\']'},
                {"pattern": r'enter\s+["\']([^"\']+)["\']'},
                {"pattern": r'input\s+["\']([^"\']+)["\']'},
            ],
            'scroll': [
                {"pattern": rf"scroll\(point='{absolute_point}',\s*direction='(down|up|right|left)'\)", "coord_mode": "absolute"},
                {"pattern": rf"scroll\(point='{relative_point}',\s*direction='(down|up|right|left)'\)", "coord_mode": "relative"},
            ],
            'hotkey': [
                {"pattern": r"hotkey\(key='([^']+)'\)"},
            ],
            'wait': [
                {"pattern": r"wait\(\)"},
                {"pattern": r'wait\s+(\d+(?:\.\d+)?)\s*seconds?'},
            ],
            'finished': [
                {"pattern": r"finished\(content='([^']+)'\)"},
                {"pattern": r"finished\(content=\"([^\"]+)\"\)"},
                {"pattern": r"finished\(\)"},
                {"pattern": r"finished\s*\(\s*\)"},
            ]
        }
    
    def parse_response(self, response: str) -> List[Action]:
        """Parse ui-tars response into a list of actions."""
        actions: List[Action] = []
        segments = self._extract_action_segments(response)

        for line_num, segment in enumerate(segments, 1):
            action = self._parse_line(segment, line_num)
            if action:
                actions.append(action)

        logger.debug(f"Parsed {len(actions)} actions from response")
        return actions

    def _extract_action_segments(self, response: str) -> List[str]:
        """Extract individual action segments from the model response."""
        segments: List[str] = []
        for raw_line in response.splitlines():
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('```'):
                continue
            if re.match(r'^thought\b', line, re.IGNORECASE):
                continue

            # Remove markdown bullets or numbering
            line = re.sub(r'^[\-\*]\s*', '', line)
            line = re.sub(r'^\d+[\.)]\s*', '', line)

            # Strip leading labels like "Action:" or "Action 1:"
            label_match = re.match(r'^(?:actions?|action\s*\d+|step\s*\d+)\s*[:\-]\s*(.*)$', line, flags=re.IGNORECASE)
            if label_match:
                line = label_match.group(1).strip()

            if not line:
                continue

            segments.extend(self._split_into_actions(line))

        return segments

    def _split_into_actions(self, text: str) -> List[str]:
        """Split a line of text into individual action strings."""
        text = text.strip().strip('`')
        if not text:
            return []

        action_keyword_pattern = re.compile(
            r'(click|left_double|right_single|drag|type|scroll|hotkey|wait|finished)\s*\(',
            re.IGNORECASE,
        )
        matches = list(action_keyword_pattern.finditer(text))

        if not matches:
            return [text]

        segments: List[str] = []
        for idx, match in enumerate(matches):
            start = match.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            segment = text[start:end].strip().strip(';').strip(',')
            if segment:
                segments.append(segment)

        return segments
    
    def _parse_line(self, line: str, line_num: int) -> Optional[Action]:
        """Parse a single line into an action."""
        original_line = line.strip()
        if not original_line:
            return None

        cleaned_line = re.sub(r'^(?:actions?|action\s*\d+|step\s*\d+)\s*[:\-]\s*', '', original_line, flags=re.IGNORECASE)
        cleaned_line = re.sub(r'^[\-\*]\s*', '', cleaned_line)
        cleaned_line = re.sub(r'^\d+[\.)]\s*', '', cleaned_line)
        cleaned_line = cleaned_line.strip()

        if not cleaned_line:
            return None

        line_lower = cleaned_line.lower()

        # Try click patterns
        for pattern_info in self.action_patterns['click']:
            pattern = pattern_info['pattern']
            match = re.search(pattern, line_lower)
            if match:
                groups = match.groups()
                if len(groups) < 2:
                    continue
                x, y = map(float, groups[:2])
                action_type = pattern_info.get("action_type", "click")
                coord_mode = pattern_info.get("coord_mode", "absolute")
                return Action(
                    type=action_type,
                    x=x,
                    y=y,
                    coord_mode=coord_mode,
                    description=original_line
                )

        # Try drag patterns
        for pattern_info in self.action_patterns['drag']:
            pattern = pattern_info['pattern']
            match = re.search(pattern, line_lower)
            if match:
                groups = match.groups()
                if len(groups) < 4:
                    continue
                start_x, start_y, end_x, end_y = map(float, groups[:4])
                return Action(
                    type='drag',
                    x=start_x,
                    y=start_y,
                    end_x=end_x,
                    end_y=end_y,
                    coord_mode=pattern_info.get("coord_mode_start", "absolute"),
                    end_coord_mode=pattern_info.get("coord_mode_end", "absolute"),
                    description=original_line
                )

        # Try type with coordinates (click first, then type)
        type_coord_pattern = r"type\s+[\"']?([^\"']+)[\"']?\s+(?:at\s+)?\(?(\d+(?:\.\d+)?),\s*(\d+(?:\.\d+)?)\)?"

        match = re.search(type_coord_pattern, line_lower)
        if match:
            text, x, y = match.groups()
            return Action(
                type='type_at',
                text=text,
                x=float(x),
                y=float(y),
                description=original_line
            )

        # Try type patterns
        for pattern_info in self.action_patterns['type']:
            match = re.search(pattern_info['pattern'], line_lower)
            if match:
                text = match.group(1)
                return Action(
                    type='type',
                    text=text,
                    description=original_line
                )

        # Try scroll patterns
        for pattern_info in self.action_patterns['scroll']:
            pattern = pattern_info['pattern']
            match = re.search(pattern, line_lower)
            if match:
                groups = match.groups()
                if len(groups) < 3:
                    continue
                x_str, y_str, direction = groups[:3]
                return Action(
                    type='scroll',
                    x=float(x_str),
                    y=float(y_str),
                    text=direction,
                    coord_mode=pattern_info.get("coord_mode", "absolute"),
                    description=original_line
                )

        # Try hotkey patterns
        for pattern_info in self.action_patterns['hotkey']:
            match = re.search(pattern_info['pattern'], line_lower)
            if match:
                key = match.group(1)
                return Action(
                    type='hotkey',
                    text=key,
                    description=original_line
                )

        # Try wait patterns
        for pattern_info in self.action_patterns['wait']:
            pattern = pattern_info['pattern']
            match = re.search(pattern, line_lower)
            if match:
                duration = 5.0 if pattern == r"wait\(\)" else float(match.group(1))
                return Action(
                    type='wait',
                    duration=duration,
                    description=original_line
                )

        # Try finished patterns
        for pattern_info in self.action_patterns['finished']:
            match = re.search(pattern_info['pattern'], line_lower)
            if match:
                if len(match.groups()) > 0 and match.group(1):
                    content = match.group(1)
                else:
                    content = "CAPTCHA solved successfully"
                return Action(
                    type='finished',
                    text=content,
                    description=original_line
                )

        logger.debug(f"Could not parse line {line_num}: {original_line}")
        return None

    def _normalize_coordinate(self, value: Optional[float], max_value: int, mode: str) -> Optional[int]:
        """Convert coordinates to absolute pixels and clamp within bounds."""
        if value is None:
            return None

        try:
            numeric = float(value)
        except (TypeError, ValueError):
            logger.warning(f"Invalid coordinate value: {value}")
            return None

        if mode == "relative" and max_value > 0:
            numeric *= max_value

        clamped = max(0.0, min(numeric, float(max_value)))
        if clamped != numeric:
            logger.warning(
                f"Coordinate {numeric} out of bounds for size {max_value}. Clamping to valid range"
            )

        return int(round(clamped))

    def validate_actions(self, actions: List[Action], image_width: int, image_height: int) -> List[Action]:
        """Validate actions and adjust coordinates if needed."""
        validated_actions = []
        
        for action in actions:
            if action.type in {'click', 'left_double', 'right_single', 'type_at', 'scroll'}:
                action.x = self._normalize_coordinate(action.x, image_width, getattr(action, "coord_mode", "absolute"))
                action.y = self._normalize_coordinate(action.y, image_height, getattr(action, "coord_mode", "absolute"))

                if action.x is None or action.y is None:
                    logger.warning(f"Action missing coordinates: {action.description}")
                    continue

                validated_actions.append(action)
                continue

            if action.type == 'drag':
                start_mode = getattr(action, "coord_mode", "absolute")
                end_mode = getattr(action, "end_coord_mode", start_mode)

                action.x = self._normalize_coordinate(action.x, image_width, start_mode)
                action.y = self._normalize_coordinate(action.y, image_height, start_mode)
                action.end_x = self._normalize_coordinate(action.end_x, image_width, end_mode)
                action.end_y = self._normalize_coordinate(action.end_y, image_height, end_mode)

                if None in (action.x, action.y, action.end_x, action.end_y):
                    logger.warning(f"Drag action missing coordinates: {action.description}")
                    continue

                validated_actions.append(action)
                continue

            validated_actions.append(action)
        
        return validated_actions
