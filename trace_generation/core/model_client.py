import base64
import io
import os
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional, Sequence

import openai
from PIL import Image


GenerationFn = Callable[[str, Optional[Sequence[str]]], Optional[str]]

from .config import (
    ACTOR_API_KEY,
    ACTOR_MODEL,
    ACTOR_BASE_URL,
    ACTOR_TEMPERATURE,
    ACTOR_TOP_P,
    ACTOR_MAX_COMPLETION_TOKENS,
    REASONER_API_KEY,
    REASONER_MODEL,
    REASONER_BASE_URL,
    REASONER_MAX_OUTPUT_TOKENS,
    REASONER_MAX_ATTEMPTS,
)


def _encode_image_to_data_uri(image_path: str) -> Optional[str]:
    """Encode image file to data URI expected by providers that accept inline images."""
    if not image_path:
        return None
    try:
        with open(image_path, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        print(f"Warning: failed to read image for reasoning prompt ({exc}).")
        return None

    extension = os.path.splitext(image_path)[1].lower()
    mime_type = "image/png"
    if extension in {".jpg", ".jpeg"}:
        mime_type = "image/jpeg"
    elif extension == ".webp":
        mime_type = "image/webp"

    return f"data:{mime_type};base64,{encoded}"


def _load_openai_provider() -> Optional[GenerationFn]:
    """Create an OpenAI-backed generation function if credentials are available."""
    from openai import OpenAI
    api_key = REASONER_API_KEY
    base_url = REASONER_BASE_URL.strip()
    if not api_key:
        if base_url.startswith("http://localhost") or base_url.startswith("http://127.0.0.1"):
            api_key = "EMPTY"
        else:
            print("Warning: reasoning provider not configured (missing REASONER_API_KEY).")
            return None

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )
    model_name = REASONER_MODEL
    max_tokens = REASONER_MAX_OUTPUT_TOKENS

    def _generate(prompt: str, image_paths: Optional[Sequence[str]]) -> Optional[str]:
        content = [{"type": "input_text", "text": prompt}]
        if image_paths:
            for image_path in image_paths:
                image_data_uri = _encode_image_to_data_uri(image_path) if image_path else None
                if image_data_uri:
                    content.append({"type": "input_image", "image_url": image_data_uri})

        try:
            response = client.responses.create(
                model=model_name,
                input=[{"role": "user", "content": content}],
                max_output_tokens=max_tokens,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"Warning: failed to generate reasoning via OpenAI ({exc}).")
            return None

        reasoning = getattr(response, "output_text", "") or ""
        return reasoning.strip()

    return _generate


def generate_reasoning(prompt: str, image_paths: Optional[Sequence[str]] = None) -> str:
    """Generate reasoning text via the OpenAI reasoning provider."""
    generator = _load_openai_provider()
    if generator is None:
        raise RuntimeError(
            "Reasoning model is not configured. Set REASONER_API_KEY (and REASONER_BASE_URL for non-OpenAI providers)."
        )
    attempts = REASONER_MAX_ATTEMPTS
    attempts = max(1, attempts)

    result: Optional[str] = None
    for attempt in range(1, attempts + 1):
        result = generator(prompt, image_paths)
        if result and result.strip():
            return result.strip()
        if attempt < attempts:
            print(f"Warning: reasoning attempt {attempt} returned no content; retrying...")
    raise RuntimeError("Reasoning generation failed after all retries.")


# ============================================================================
# Agent classes for CAPTCHA solving
# ============================================================================

class Agent(ABC):
    """Abstract base class for agents that solve CAPTCHAs."""

    @abstractmethod
    def __call__(
        self,
        prompt: str,
        images: Optional[list[Image.Image]] = None,
        image_captions: Optional[list[str]] = None,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Generate a response to solve the CAPTCHA.

        Args:
            prompt: The user prompt/instruction
            images: Optional list of PIL images
            image_captions: Optional captions for each image
            system_prompt: Optional system prompt to set context

        Returns:
            Model's response text
        """
        pass

    @abstractmethod
    def reset(self):
        """Reset the agent's conversation history."""
        pass


class GPTAgent(Agent):
    """
    Agent that calls OpenAI-compatible APIs for CAPTCHA solving.
    Supports system prompts and maintains conversation history.
    """

    def __init__(self, system_prompt: Optional[str] = None) -> None:
        """
        Initialize the GPT agent.

        Args:
            system_prompt: Optional default system prompt
        """
        actor_api_key = ACTOR_API_KEY
        if not actor_api_key and (
            ACTOR_BASE_URL.startswith("http://localhost")
            or ACTOR_BASE_URL.startswith("http://127.0.0.1")
        ):
            actor_api_key = "EMPTY"

        self.model = ACTOR_MODEL
        self.client = openai.OpenAI(
            api_key=actor_api_key,
            base_url=ACTOR_BASE_URL
        )
        self.history = []
        self.default_system_prompt = system_prompt

        # Initialize history with system prompt if provided
        if system_prompt:
            self.history.append({"role": "system", "content": system_prompt})

    def reset(self):
        """Reset conversation history, preserving default system prompt if set."""
        self.history = []
        if self.default_system_prompt:
            self.history.append({"role": "system", "content": self.default_system_prompt})

    def __call__(
        self,
        prompt: str,
        images: Optional[list[Image.Image]] = None,
        image_captions: Optional[list[str]] = None,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Generate a response using the GPT model.

        Args:
            prompt: The user prompt/instruction
            images: Optional list of PIL images
            image_captions: Optional captions for each image
            system_prompt: Optional system prompt for this specific call

        Returns:
            Model's response text
        """
        # Add system prompt for this specific call if provided
        if system_prompt and (not self.history or self.history[0].get("role") != "system"):
            self.history.insert(0, {"role": "system", "content": system_prompt})
        elif system_prompt and self.history and self.history[0].get("role") == "system":
            # Update existing system prompt
            self.history[0] = {"role": "system", "content": system_prompt}

        # Build user message content
        user_prompt: list[dict[str, Any]] = [{"type": "text", "text": prompt}]

        if images:
            for i, image in enumerate(images):
                bytes_io = io.BytesIO()
                image.save(bytes_io, format="JPEG")
                image_b64 = base64.b64encode(bytes_io.getvalue()).decode('ascii')

                # Add image caption if provided, otherwise use default
                if image_captions and i < len(image_captions):
                    user_prompt.append({
                        "type": "text",
                        "text": image_captions[i]
                    })
                else:
                    user_prompt.append({
                        "type": "text",
                        "text": f"Image {i+1}"
                    })

                user_prompt.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}
                })

        self.history.append({"role": "user", "content": user_prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.history,
            max_completion_tokens=ACTOR_MAX_COMPLETION_TOKENS,
            temperature=ACTOR_TEMPERATURE,
            top_p=ACTOR_TOP_P
        )

        content = response.choices[0].message.content
        if content is None:
            content = ""

        self.history.append({"role": "assistant", "content": content})

        return content
