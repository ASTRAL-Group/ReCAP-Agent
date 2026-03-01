#!/usr/bin/env python3
"""Prompt processing for the CAPTCHA evaluation framework."""

from __future__ import annotations
from typing import Dict, List, Optional
from utils import get_logger

logger = get_logger(__name__)


class PromptProcessor:
    """Handles prompt processing and context building for the agent."""

    def __init__(
        self,
        base_prompt: str,
        subsequent_prompt: str,
    ) -> None:
        self.base_prompt = base_prompt
        self.subsequent_prompt = subsequent_prompt

    def reset_conversation(self) -> None:
        pass

    def build_context_from_actions(self, previous_action_rounds: List[Dict]) -> str:
        if not previous_action_rounds:
            return ""

        context = "\n\n## Previous Actions Taken:\n"
        for default_round_idx, round_entry in enumerate(previous_action_rounds, 1):
            round_idx = round_entry.get("round", default_round_idx)
            actions = round_entry.get("actions", [])
            if not actions:
                context += f"Round {round_idx}: No action parsed\n"
                continue
            action_texts = [self._format_action_summary(action) for action in actions]
            context += f"Round {round_idx}: " + "; ".join(action_texts) + "\n"
        return context

    def process_prompt(
        self,
        call_count: int,
        previous_action_rounds: Optional[List[Dict]] = None,
    ) -> str:
        if call_count == 1:
            return self.base_prompt

        brief_prompt = self.subsequent_prompt
        if previous_action_rounds:
            brief_prompt += self.build_context_from_actions(previous_action_rounds)
        else:
            brief_prompt += f"\nThis is call {call_count}. Continue solving the CAPTCHA based on the current state."
        return brief_prompt

    def check_finished(self, call_count: int, actions: List[Dict]) -> bool:
        """Track whether the model emitted a finish/terminate signal."""
        finished = any(action.get("type") in {"finished", "terminate"} for action in actions)
        if finished:
            logger.debug("Model indicated CAPTCHA is finished on call %s", call_count)
        return finished

    def _format_action_summary(self, action: Dict) -> str:
        action_type = action.get("type", "unknown")

        if action_type == "click":
            x, y = action.get("x", "?"), action.get("y", "?")
            return f"Clicked at ({x}, {y})"
        if action_type == "type":
            text = action.get("text", "")
            return f"Typed '{text}'"
        if action_type == "drag":
            x1, y1 = action.get("x", "?"), action.get("y", "?")
            x2, y2 = action.get("end_x", "?"), action.get("end_y", "?")
            return f"Dragged from ({x1}, {y1}) to ({x2}, {y2})"
        if action_type == "wait":
            return "Waited"
        if action_type in {"finished", "terminate"}:
            return "Indicated finished"
        if action_type == "scroll":
            x, y = action.get("x", "?"), action.get("y", "?")
            direction = action.get("text", "unknown")
            return f"Scrolled {direction} at ({x}, {y})"
        if action_type == "hotkey":
            key = action.get("text", "unknown")
            return f"Pressed hotkey '{key}'"
        return str(action_type)
