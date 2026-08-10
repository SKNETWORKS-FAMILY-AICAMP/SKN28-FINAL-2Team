from __future__ import annotations

import json
import os
from typing import Any

DEFAULT_CHAT_MODEL = "gpt-4o-mini"


class LLMClientError(RuntimeError):
    """Raised when the LLM client cannot be built or its response is unusable."""


class OpenAIChatClient:
    def __init__(
        self,
        *,
        api_key: str | None,
        model: str | None = None,
        temperature: float | None = None,
        client: Any | None = None,
    ) -> None:
        if not api_key:
            raise LLMClientError("OPENAI_API_KEY is required to build an OpenAIChatClient")
        if client is None:
            try:
                import openai
            except ImportError as exc:  # pragma: no cover - environment dependent
                raise LLMClientError("the 'openai' package is not installed") from exc

            client = openai.OpenAI(api_key=api_key)

        self._client = client
        self.model = model or os.environ.get("OPENAI_CHAT_MODEL", DEFAULT_CHAT_MODEL)
        self.temperature = temperature

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        request: dict[str, Any] = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if self.temperature is not None:
            request["temperature"] = self.temperature

        response = self._client.chat.completions.create(**request)
        content = response.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMClientError(f"model did not return valid JSON: {exc}") from exc
