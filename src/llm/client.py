from __future__ import annotations

import json
import os
from typing import Any

DEFAULT_CHAT_MODEL = "gpt-5.6-luna"
DEFAULT_REASONING_EFFORT = "low"


class LLMClientError(RuntimeError):
    """Raised when the LLM client cannot be built or its response is unusable."""


class OpenAIChatClient:
    def __init__(
        self,
        *,
        api_key: str | None,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> None:
        if not api_key:
            raise LLMClientError(
                "OPENAI_API_KEY is required to build an OpenAIChatClient"
            )

        try:
            import openai
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise LLMClientError(
                "the 'openai' package is not installed"
            ) from exc

        self._client = openai.OpenAI(api_key=api_key)
        self.model = (
            model
            or os.environ.get("OPENAI_CHAT_MODEL")
            or DEFAULT_CHAT_MODEL
        )
        self.reasoning_effort = os.environ.get(
            "OPENAI_REASONING_EFFORT",
            DEFAULT_REASONING_EFFORT,
        )
        self.temperature = temperature

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        request: dict[str, Any] = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        if self.model.startswith("gpt-5.6"):
            request["reasoning_effort"] = self.reasoning_effort
        else:
            request["temperature"] = self.temperature

        response = self._client.chat.completions.create(**request)
        content = response.choices[0].message.content or "{}"

        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMClientError(
                f"model did not return valid JSON: {exc}"
            ) from exc