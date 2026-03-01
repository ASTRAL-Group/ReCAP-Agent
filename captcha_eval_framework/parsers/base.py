#!/usr/bin/env python3
"""Base parser classes and registry for action parsers."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple, Type

from actions import Action
from utils import get_logger

logger = get_logger(__name__)


class ActionParserMeta(type):
    """Metaclass registry for action parsers."""

    registry: Dict[str, Type["ActionParser"]] = {}

    def __new__(mcls, name, bases, attrs):
        cls = super().__new__(mcls, name, bases, attrs)
        parser_name = attrs.get("name")
        if parser_name:
            mcls.registry[parser_name] = cls
        return cls


class ActionParser(metaclass=ActionParserMeta):
    """Base class for action parsers."""

    name: Optional[str] = None
    coordinate_grid: Optional[int] = None

    def parse_response(self, response: str) -> List[Action]:
        raise NotImplementedError

    def validate_actions(self, actions: List[Action], image_width: int, image_height: int) -> List[Action]:
        validated: List[Action] = []

        for action in actions:
            if action.type in {
                "click",
                "left_double",
                "right_single",
                "type_at",
                "scroll",
                "double_click",
                "right_click",
                "middle_click",
                "mouse_move",
                "drag_to",
            }:
                action.x = self._convert_coordinate(action.x, image_width, action.coord_mode)
                action.y = self._convert_coordinate(action.y, image_height, action.coord_mode)

                if action.type != "scroll" and (action.x is None or action.y is None):
                    logger.debug("Dropping action with missing coordinates: %s", action.description)
                    continue

                validated.append(action)
                continue

            if action.type == "drag":
                action.x = self._convert_coordinate(action.x, image_width, action.coord_mode)
                action.y = self._convert_coordinate(action.y, image_height, action.coord_mode)
                action.end_x = self._convert_coordinate(action.end_x, image_width, action.coord_mode)
                action.end_y = self._convert_coordinate(action.end_y, image_height, action.coord_mode)

                if None in (action.x, action.y, action.end_x, action.end_y):
                    logger.debug("Dropping drag action with missing coordinates: %s", action.description)
                    continue

                validated.append(action)
                continue

            validated.append(action)

        return validated

    def _convert_coordinate(self, value: Optional[float], max_value: int, mode: str) -> Optional[int]:
        if value is None:
            return None

        try:
            numeric = float(value)
        except (TypeError, ValueError):
            logger.debug("Invalid coordinate value: %s", value)
            return None

        if mode == "relative" and max_value > 0:
            numeric *= max_value
        elif mode == "grid" and max_value > 0:
            grid = self.coordinate_grid or 1000
            denom = max(1, grid - 1)
            numeric = numeric * (max_value / denom)

        clamped = max(0.0, min(numeric, float(max_value)))
        if clamped != numeric:
            logger.debug(
                "Coordinate %s out of bounds for size %s. Clamping to valid range",
                numeric,
                max_value,
            )

        return int(round(clamped))


class CompositeActionParser:
    """Attempts multiple parsers and returns the first successful parse."""

    def __init__(self, parsers: Sequence[ActionParser]):
        self.parsers = list(parsers)

    def parse_response(self, response: str, image_width: int, image_height: int) -> List[Action]:
        for parser in self.parsers:
            actions = parser.parse_response(response)
            if not actions:
                continue
            return parser.validate_actions(actions, image_width, image_height)

        return []
