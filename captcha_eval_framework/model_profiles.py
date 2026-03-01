#!/usr/bin/env python3
"""Model family registry for parser, prompt, and agent selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict

from agent import Agent, CUAAgent, GPTAgent
from parsers.base import CompositeActionParser
from parsers.cua_parser import ComputerCallActionParser
from parsers.point_parser import PointActionParser
from parsers.tool_call_parser import ToolCallActionParser
from prompt import (
    BASE_PROMPT_QWEN3,
    BASE_PROMPT_UI_OPENAI_CUA,
    BASE_PROMPT_UI_TARS,
    SUBSEQUENT_PROMPT_DEFAULT,
)


@dataclass(frozen=True)
class ModelProfile:
    name: str
    agent_factory: Callable[[], Agent]
    parser_factory: Callable[[], CompositeActionParser]
    base_prompt: str
    subsequent_prompt: str


MODEL_PROFILES: Dict[str, ModelProfile] = {
    "qwen3": ModelProfile(
        name="qwen3",
        agent_factory=GPTAgent,
        parser_factory=lambda: CompositeActionParser([ToolCallActionParser()]),
        base_prompt=BASE_PROMPT_QWEN3,
        subsequent_prompt=SUBSEQUENT_PROMPT_DEFAULT,
    ),
    "ui-tars": ModelProfile(
        name="ui-tars",
        agent_factory=GPTAgent,
        parser_factory=lambda: CompositeActionParser([PointActionParser()]),
        base_prompt=BASE_PROMPT_UI_TARS,
        subsequent_prompt=SUBSEQUENT_PROMPT_DEFAULT,
    ),
    "openai-cua": ModelProfile(
        name="openai-cua",
        agent_factory=CUAAgent,
        parser_factory=lambda: CompositeActionParser([ComputerCallActionParser()]),
        base_prompt=BASE_PROMPT_UI_OPENAI_CUA,
        subsequent_prompt=SUBSEQUENT_PROMPT_DEFAULT,
    ),
}


def get_model_profile(model_family: str) -> ModelProfile:
    profile = MODEL_PROFILES.get(model_family)
    if profile is None:
        available = ", ".join(sorted(MODEL_PROFILES.keys()))
        raise ValueError(f"Unknown model family '{model_family}'. Available: {available}")
    return profile
