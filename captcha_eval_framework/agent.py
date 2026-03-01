#!/usr/bin/env python3
"""Agent integrations for the CAPTCHA evaluation framework."""

from __future__ import annotations

import base64
import io
import json
import os
from abc import ABC, abstractmethod
from typing import Any, Optional

import openai
from PIL import Image

from utils import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_BASE_URL,
    MODEL_MAX_COMPLETION_TOKENS,
    MODEL_TEMPERATURE,
    MODEL_TOP_P,
    BROWSER_VIEWPORT,
    OPENAI_CUA_ENVIRONMENT,
    OPENAI_CUA_MODEL,
    OPENAI_CUA_REASONING_SUMMARY,
)
OPENAI_CUA_DISPLAY_WIDTH = int(
    os.getenv("OPENAI_CUA_DISPLAY_WIDTH", str(BROWSER_VIEWPORT["width"]))
)
OPENAI_CUA_DISPLAY_HEIGHT = int(
    os.getenv("OPENAI_CUA_DISPLAY_HEIGHT", str(BROWSER_VIEWPORT["height"]))
)


class Agent(ABC):
    @abstractmethod
    def __call__(
        self,
        prompt: str,
        images: Optional[list[Image.Image]] = None,
        image_captions: Optional[list[str]] = None,
    ) -> str:
        pass

    @abstractmethod
    def reset(self) -> None:
        pass


class GPTAgent(Agent):
    """OpenAI-compatible multimodal agent."""

    def __init__(self) -> None:
        self.model = OPENAI_MODEL
        self.client = openai.OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        self.history: list[dict[str, Any]] = []

    def reset(self) -> None:
        self.history = []

    def __call__(
        self,
        prompt: str,
        images: Optional[list[Image.Image]] = None,
        image_captions: Optional[list[str]] = None,
    ) -> str:
        user_prompt: list[dict[str, Any]] = [{"type": "text", "text": prompt}]

        if images:
            for i, image in enumerate(images):
                bytes_io = io.BytesIO()
                image.save(bytes_io, format="JPEG")
                image_b64 = base64.b64encode(bytes_io.getvalue()).decode("ascii")

                caption = f"Image {i + 1}"
                if image_captions and i < len(image_captions) and image_captions[i]:
                    caption = image_captions[i]

                user_prompt.append({"type": "text", "text": caption})
                user_prompt.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                    }
                )

        self.history.append({"role": "user", "content": user_prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.history,
            max_completion_tokens=MODEL_MAX_COMPLETION_TOKENS,
            temperature=MODEL_TEMPERATURE,
            top_p=MODEL_TOP_P,
        )

        content = response.choices[0].message.content or ""

        self.history.append({"role": "assistant", "content": content})
        return content


class CUAAgent(Agent):
    """OpenAI computer_use_preview agent."""

    def __init__(self) -> None:
        self.model = OPENAI_CUA_MODEL
        self.environment = OPENAI_CUA_ENVIRONMENT
        self.display_width = OPENAI_CUA_DISPLAY_WIDTH
        self.display_height = OPENAI_CUA_DISPLAY_HEIGHT
        self.reasoning_summary = OPENAI_CUA_REASONING_SUMMARY
        self.client = openai.OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        self.previous_response_id: Optional[str] = None
        self.last_call_id: Optional[str] = None
        self.pending_safety_checks: list[dict[str, Any]] = []

    def reset(self) -> None:
        self.previous_response_id = None
        self.last_call_id = None
        self.pending_safety_checks = []

    def __call__(
        self,
        prompt: str,
        images: Optional[list[Image.Image]] = None,
        image_captions: Optional[list[str]] = None,
    ) -> str:
        image_url = None
        if images:
            image_url = self._encode_image(images[0])

        use_call_output = bool(self.previous_response_id and self.last_call_id and image_url)

        if use_call_output:
            input_items: list[dict[str, Any]] = [
                {
                    "type": "computer_call_output",
                    "call_id": self.last_call_id,
                    "output": {"type": "input_image", "image_url": image_url},
                }
            ]
            if self.pending_safety_checks:
                input_items[0]["acknowledged_safety_checks"] = self.pending_safety_checks
                self.pending_safety_checks = []
        else:
            content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]
            if image_url:
                content.append({"type": "input_image", "image_url": image_url})
            input_items = [{"role": "user", "content": content}]

        request: dict[str, Any] = {
            "model": self.model,
            "tools": [
                {
                    "type": "computer_use_preview",
                    "display_width": self.display_width,
                    "display_height": self.display_height,
                    "environment": self.environment,
                }
            ],
            "input": input_items,
            "truncation": "auto",
        }
        if use_call_output:
            request["previous_response_id"] = self.previous_response_id
        if self.reasoning_summary:
            request["reasoning"] = {"summary": self.reasoning_summary}

        response = self.client.responses.create(**request)
        self.previous_response_id = getattr(response, "id", None)

        output_items = self._normalize_output_items(getattr(response, "output", []))
        self._update_call_state(output_items)

        payload = {"output": output_items}
        return json.dumps(payload, ensure_ascii=True)

    def _encode_image(self, image: Image.Image) -> str:
        bytes_io = io.BytesIO()
        image.save(bytes_io, format="PNG")
        image_b64 = base64.b64encode(bytes_io.getvalue()).decode("ascii")
        return f"data:image/png;base64,{image_b64}"

    def _update_call_state(self, output_items: list[dict[str, Any]]) -> None:
        self.last_call_id = None
        self.pending_safety_checks = []
        for item in output_items:
            if item.get("type") != "computer_call":
                continue
            self.last_call_id = item.get("call_id")
            checks = item.get("pending_safety_checks") or []
            if isinstance(checks, list):
                self.pending_safety_checks = [
                    check for check in checks if isinstance(check, dict)
                ]
            break

    def _normalize_output_items(self, items: Any) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        if not items:
            return normalized
        for item in items:
            normalized.append(self._normalize_item(item))
        return normalized

    def _normalize_item(self, item: Any) -> dict[str, Any]:
        if isinstance(item, dict):
            return self._coerce_nested(item)
        for attr in ("model_dump", "dict", "to_dict"):
            if hasattr(item, attr):
                try:
                    data = getattr(item, attr)()
                    if isinstance(data, dict):
                        return self._coerce_nested(data)
                except Exception:
                    pass
        try:
            data = dict(item)
            if isinstance(data, dict):
                return self._coerce_nested(data)
        except Exception:
            pass

        fallback: dict[str, Any] = {}
        for key in ("type", "call_id", "action", "pending_safety_checks", "id", "status"):
            value = getattr(item, key, None)
            if value is not None:
                fallback[key] = self._coerce_nested(value)
        return fallback

    def _coerce_nested(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {k: self._coerce_nested(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._coerce_nested(v) for v in value]
        for attr in ("model_dump", "dict", "to_dict"):
            if hasattr(value, attr):
                try:
                    data = getattr(value, attr)()
                    return self._coerce_nested(data)
                except Exception:
                    pass
        if hasattr(value, "__dict__"):
            return self._coerce_nested(value.__dict__)
        return value
