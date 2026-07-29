from __future__ import annotations

import json
import os
from typing import Any, Mapping, Protocol, Sequence

from .models import ItineraryDraft, TravelConditions
from .prompts import (
    CONDITION_EXTRACTION_SYSTEM_PROMPT,
    CONDITION_PROMPT_VERSION,
    ITINERARY_GENERATION_SYSTEM_PROMPT,
    ITINERARY_PROMPT_VERSION,
    REPAIR_PROMPT_VERSION,
    repair_system_prompt,
)
from .schemas import CONDITION_OUTPUT_SCHEMA, ITINERARY_OUTPUT_SCHEMA


class LLMError(RuntimeError):
    """Raised when the LLM cannot return a valid structured response."""


class TravelLLM(Protocol):
    def extract_conditions(
        self,
        *,
        message: str,
        history: Sequence[Mapping[str, str]] = (),
        current_conditions: Mapping[str, Any] | None = None,
    ) -> TravelConditions: ...

    def generate_itinerary(self, context: Mapping[str, Any]) -> ItineraryDraft: ...

    def repair_itinerary(
        self,
        *,
        context: Mapping[str, Any],
        invalid_draft: ItineraryDraft,
        validation_messages: Sequence[str],
    ) -> ItineraryDraft: ...


class OpenAITravelLLM:
    """OpenAI Responses API adapter using strict JSON Schema outputs."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 45.0,
        client: Any | None = None,
    ) -> None:
        self.model = (
            model or os.environ.get("OPENAI_CHAT_MODEL") or "gpt-5-mini"
        )
        if client is None:
            key = api_key or os.environ.get("OPENAI_API_KEY", "")
            if not key:
                raise LLMError("OPENAI_API_KEY is not configured")
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise LLMError(
                    "openai is not installed; run: pip install -r requirements.txt"
                ) from exc
            client = OpenAI(api_key=key, timeout=timeout)
        self._client = client

    def extract_conditions(
        self,
        *,
        message: str,
        history: Sequence[Mapping[str, str]] = (),
        current_conditions: Mapping[str, Any] | None = None,
    ) -> TravelConditions:
        payload = {
            "latest_message": message,
            "recent_history": list(history)[-8:],
            "current_conditions": dict(current_conditions or {}),
            "prompt_version": CONDITION_PROMPT_VERSION,
        }
        parsed = self._structured_response(
            system_prompt=CONDITION_EXTRACTION_SYSTEM_PROMPT,
            payload=payload,
            schema_name="travel_condition_extraction",
            schema=CONDITION_OUTPUT_SCHEMA,
            max_output_tokens=2400,
        )
        try:
            return TravelConditions.from_mapping(parsed)
        except (KeyError, TypeError, ValueError) as exc:
            raise LLMError(
                f"LLM condition output failed domain validation: {exc}"
            ) from exc

    def generate_itinerary(self, context: Mapping[str, Any]) -> ItineraryDraft:
        payload = {
            **dict(context),
            "prompt_version": ITINERARY_PROMPT_VERSION,
        }
        parsed = self._structured_response(
            system_prompt=ITINERARY_GENERATION_SYSTEM_PROMPT,
            payload=payload,
            schema_name="tourapi_itinerary_draft",
            schema=ITINERARY_OUTPUT_SCHEMA,
            max_output_tokens=3500,
        )
        try:
            return ItineraryDraft.from_mapping(parsed)
        except (KeyError, TypeError, ValueError) as exc:
            raise LLMError(
                f"LLM itinerary output failed domain validation: {exc}"
            ) from exc

    def repair_itinerary(
        self,
        *,
        context: Mapping[str, Any],
        invalid_draft: ItineraryDraft,
        validation_messages: Sequence[str],
    ) -> ItineraryDraft:
        messages = [str(message) for message in validation_messages]
        payload = {
            **dict(context),
            "invalid_draft": invalid_draft.to_dict(),
            "validation_errors": messages,
            "prompt_version": REPAIR_PROMPT_VERSION,
        }
        parsed = self._structured_response(
            system_prompt=repair_system_prompt(messages),
            payload=payload,
            schema_name="repaired_tourapi_itinerary_draft",
            schema=ITINERARY_OUTPUT_SCHEMA,
            max_output_tokens=3500,
        )
        try:
            return ItineraryDraft.from_mapping(parsed)
        except (KeyError, TypeError, ValueError) as exc:
            raise LLMError(
                f"LLM repair output failed domain validation: {exc}"
            ) from exc

    def _structured_response(
        self,
        *,
        system_prompt: str,
        payload: Mapping[str, Any],
        schema_name: str,
        schema: Mapping[str, Any],
        max_output_tokens: int,
    ) -> dict[str, Any]:
        try:
            response = self._client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False),
                    },
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
                        "schema": dict(schema),
                        "strict": True,
                    }
                },
                max_output_tokens=max_output_tokens,
            )
        except Exception as exc:
            raise LLMError(f"OpenAI structured response failed: {exc}") from exc

        output_text = getattr(response, "output_text", None)
        if not output_text:
            raise LLMError("OpenAI returned no structured output")
        try:
            parsed = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise LLMError("OpenAI returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise LLMError("OpenAI structured output root must be an object")
        return parsed
