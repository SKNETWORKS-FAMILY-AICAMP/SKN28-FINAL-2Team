from __future__ import annotations

import json
import os
from typing import Any, Mapping, Protocol, Sequence

from .models import ItineraryDraft, TravelConditions
from .langsmith_observability import maybe_wrap_openai_client
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
        self.usage_records: list[dict[str, Any]] = []
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
        self._client = maybe_wrap_openai_client(client)

    def extract_conditions(
        self,
        *,
        message: str,
        history: Sequence[Mapping[str, str]] = (),
        current_conditions: Mapping[str, Any] | None = None,
    ) -> TravelConditions:
        payload = {
            "latest_message": message,
            "recent_history": _compact_history(history),
            "current_conditions": dict(current_conditions or {}),
            "prompt_version": CONDITION_PROMPT_VERSION,
        }
        parsed = self._structured_response(
            system_prompt=CONDITION_EXTRACTION_SYSTEM_PROMPT,
            payload=payload,
            schema_name="travel_condition_extraction",
            schema=CONDITION_OUTPUT_SCHEMA,
            token_budgets=_token_budgets(
                _env_int("RAG_CONDITION_MAX_OUTPUT_TOKENS", 1800)
            ),
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
        slot_count = len(context.get("slots") or ())
        output_budget = min(
            _env_int("RAG_ITINERARY_MAX_OUTPUT_TOKENS", 4500),
            max(1600, 700 + slot_count * 110),
        )
        parsed = self._structured_response(
            system_prompt=ITINERARY_GENERATION_SYSTEM_PROMPT,
            payload=payload,
            schema_name="tourapi_itinerary_draft",
            schema=ITINERARY_OUTPUT_SCHEMA,
            token_budgets=_token_budgets(output_budget),
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
        repair_context = _compact_repair_context(context)
        payload = {
            **repair_context,
            "invalid_draft": invalid_draft.to_dict(),
            "validation_errors": messages,
            "prompt_version": REPAIR_PROMPT_VERSION,
        }
        slot_count = len(repair_context.get("slots") or ())
        output_budget = min(
            _env_int("RAG_REPAIR_MAX_OUTPUT_TOKENS", 4000),
            max(1600, 700 + slot_count * 110),
        )
        parsed = self._structured_response(
            system_prompt=repair_system_prompt(messages),
            payload=payload,
            schema_name="repaired_tourapi_itinerary_draft",
            schema=ITINERARY_OUTPUT_SCHEMA,
            token_budgets=_token_budgets(output_budget),
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
        token_budgets: Sequence[int],
    ) -> dict[str, Any]:
        from .openai_responses import create_text_response

        serialized_payload = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        output_text, responses = create_text_response(
            client=self._client,
            label=f"OpenAI structured response ({schema_name})",
            request={
                "model": self.model,
                "input": [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": serialized_payload,
                    },
                ],
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
                        "schema": dict(schema),
                        "strict": True,
                    }
                },
            },
            token_budgets=token_budgets,
        )
        for attempt, response in enumerate(responses, start=1):
            usage = getattr(response, "usage", None)
            output_details = getattr(usage, "output_tokens_details", None)
            self.usage_records.append(
                {
                    "stage": schema_name,
                    "attempt": attempt,
                    "model": self.model,
                    "input_tokens": int(
                        getattr(usage, "input_tokens", 0) or 0
                    ),
                    "output_tokens": int(
                        getattr(usage, "output_tokens", 0) or 0
                    ),
                    "total_tokens": int(
                        getattr(usage, "total_tokens", 0) or 0
                    ),
                    "reasoning_tokens": int(
                        getattr(output_details, "reasoning_tokens", 0) or 0
                    ),
                    "input_characters": (
                        len(system_prompt) + len(serialized_payload)
                    ),
                    "output_token_budget": int(
                        token_budgets[min(attempt - 1, len(token_budgets) - 1)]
                    ),
                }
            )
        try:
            parsed = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise LLMError("OpenAI returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise LLMError("OpenAI structured output root must be an object")
        return parsed

    def drain_usage_records(self) -> list[dict[str, Any]]:
        """Return and clear per-call token usage for evaluation/observability."""

        records = [dict(item) for item in self.usage_records]
        self.usage_records.clear()
        return records


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _token_budgets(first_budget: int) -> tuple[int, ...]:
    """Keep empty-output retries opt-in because they resend the whole prompt."""

    retry_count = min(
        max(_env_int_allow_zero("RAG_LLM_EMPTY_RESPONSE_RETRIES", 0), 0),
        1,
    )
    if retry_count == 0:
        return (first_budget,)
    retry_cap = _env_int("RAG_LLM_RETRY_MAX_OUTPUT_TOKENS", 6000)
    return (first_budget, min(max(first_budget + 1200, first_budget), retry_cap))


def _env_int_allow_zero(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _compact_history(
    history: Sequence[Mapping[str, str]],
) -> list[dict[str, str]]:
    """Retain enough dialogue for condition updates without resending long results."""

    result: list[dict[str, str]] = []
    for item in list(history)[-4:]:
        role = str(item.get("role") or "").strip()
        content = str(item.get("content") or "").strip()
        if not role or not content:
            continue
        result.append({"role": role, "content": content[:1200]})
    return result


def _compact_repair_context(
    context: Mapping[str, Any],
) -> dict[str, Any]:
    """Remove explanatory retrieval fields that are not needed for ID repair."""

    slots: list[dict[str, Any]] = []
    for raw_slot in context.get("slots") or ():
        if not isinstance(raw_slot, Mapping):
            continue
        candidates = []
        for raw_candidate in raw_slot.get("tourapi_candidates") or ():
            if not isinstance(raw_candidate, Mapping):
                continue
            candidates.append(
                {
                    key: raw_candidate.get(key)
                    for key in (
                        "content_id",
                        "title",
                        "itinerary_role",
                        "opening_hours",
                        "closed_days",
                        "parking",
                        "distance_km",
                        "rating",
                        "slot_score",
                    )
                }
            )
        slots.append(
            {
                key: raw_slot.get(key)
                for key in (
                    "day",
                    "slot_sequence",
                    "role",
                    "category",
                    "slot_kind",
                    "meal_type",
                    "suggested_stay_minutes",
                    "allowed_content_ids",
                )
            }
            | {"tourapi_candidates": candidates}
        )
    return {
        "input_mode": context.get("input_mode"),
        "user_conditions": context.get("user_conditions", {}),
        "slots": slots,
        "policy": context.get("policy", {}),
    }
