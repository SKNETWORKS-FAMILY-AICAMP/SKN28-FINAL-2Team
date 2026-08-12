from __future__ import annotations

import os
from typing import Any

from ..models.travel_condition import ConditionDelta, TravelCondition
from .client import DEFAULT_CHAT_MODEL, LLMClientError, OpenAIChatClient
from . import prompts


class LLMService:
    """High-level LLM operations used by the itinerary engine."""

    def __init__(self, client: OpenAIChatClient) -> None:
        self._client = client

# ------------------------------------------------------------------
# 1. Condition Extraction
# ------------------------------------------------------------------
    def extract_travel_condition(self, user_text: str) -> TravelCondition:

        print("=" * 80)
        print("LLM Condition Extraction")
        print("User Text :", user_text)
        print("=" * 80)

        raw = self._client.complete_json(
            system_prompt=prompts.CONDITION_EXTRACTION_SYSTEM_PROMPT,
            user_prompt=prompts.build_condition_extraction_prompt(user_text),
        )

        print("=" * 80)
        print("LLM RAW RESPONSE")
        print(raw)
        print("=" * 80)

        try:
            condition = TravelCondition.from_mapping(raw)

            print("=" * 80)
            print("TravelCondition")
            print(condition)
            print("=" * 80)

            return condition

        except ValueError as exc:
            print("=" * 80)
            print("TravelCondition 생성 실패")
            print(raw)
            print(exc)
            print("=" * 80)

            raise LLMClientError(
                f"condition extraction returned an invalid payload: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # 3. RAG Query Generation
    # ------------------------------------------------------------------
    def generate_search_query(
        self,
        condition: TravelCondition,
        *,
        slot_role: str,
        day: int,
        extra_request: str | None = None,
    ) -> str:

        raw = self._client.complete_json(
            system_prompt=prompts.QUERY_GENERATION_SYSTEM_PROMPT,
            user_prompt=prompts.build_query_generation_prompt(
                condition.to_llm_dict(),
                slot_role=slot_role,
                day=day,
                extra_request=extra_request,
            ),
        )

        query = str(raw.get("query") or "").strip()

        if not query:
            raise LLMClientError(
                "query generation returned an empty query"
            )

        return query

    # ------------------------------------------------------------------
    # 3-b. RAG Query Generation (whole-trip, role-agnostic)
    # ------------------------------------------------------------------
    def generate_style_query(
        self,
        condition: TravelCondition,
        *,
        reference_keywords: dict[str, list[str]] | None = None,
    ) -> str:
        """Build a single broad query for the RAG candidate-pool step.

        Unlike :meth:`generate_search_query`, this is not tied to a single
        slot's role. It is used once per itinerary to gather a wide pool of
        candidates driven purely by the user's style (``preferred_visit_types``)
        and free-text wishes (``must_visit_places``), matching the "RAG"
        branch of the AIHub/RAG retrieval pipeline.

        ``reference_keywords`` (role -> representative place names, from
        Top-K similar AIHub trips' actual visit history) is optional
        supporting context: it nudges the search query toward the kind of
        places similar travelers actually visited, but it never overrides
        the user's stated condition and is never inserted into the
        itinerary directly.
        """

        raw = self._client.complete_json(
            system_prompt=prompts.STYLE_QUERY_GENERATION_SYSTEM_PROMPT,
            user_prompt=prompts.build_style_query_generation_prompt(
                condition.to_llm_dict(),
                reference_keywords=reference_keywords,
            ),
        )

        query = str(raw.get("query") or "").strip()

        if not query:
            raise LLMClientError(
                "style query generation returned an empty query"
            )

        return query

    # ------------------------------------------------------------------
    # 4. Final Itinerary Generation
    # ------------------------------------------------------------------
    def generate_itinerary(
        self,
        condition: TravelCondition,
        days_with_candidates: list[dict[str, Any]],
        *,
        movement_patterns: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        raw = self._client.complete_json(
            system_prompt=prompts.ITINERARY_GENERATION_SYSTEM_PROMPT,
            user_prompt=prompts.build_itinerary_generation_prompt(
                condition.to_llm_dict(),
                days_with_candidates,
                movement_patterns=movement_patterns,
            ),
        )

        if "days" not in raw:
            raise LLMClientError(
                "itinerary generation response is missing 'days'"
            )

        _validate_generated_itinerary(raw, days_with_candidates)

        return raw

    # ------------------------------------------------------------------
    # 5. Chat Condition Update
    # ------------------------------------------------------------------
    def extract_condition_delta(
        self,
        condition: TravelCondition,
        user_text: str,
    ) -> ConditionDelta:

        raw = self._client.complete_json(
            system_prompt=prompts.CHAT_UPDATE_SYSTEM_PROMPT,
            user_prompt=prompts.build_chat_update_prompt(
                condition.to_llm_dict(),
                user_text,
            ),
        )

        print("========== CHAT UPDATE RAW ==========")
        print(raw)
        print("=====================================")

        try:
            return ConditionDelta.from_mapping(raw)

        except (KeyError, ValueError) as exc:
            raise LLMClientError(
                f"chat-update extraction returned an invalid payload: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # 6. Itinerary Revision
    # ------------------------------------------------------------------
    def revise_itinerary(
        self,
        condition: TravelCondition,
        existing_itinerary: dict[str, Any],
        changed_slots: list[dict[str, Any]],
    ) -> dict[str, Any]:

        print("=" * 80)
        print("changed_slots")

        for slot in changed_slots:
            print(
                f"day={slot['day']} "
                f"sequence={slot['sequence']} "
                f"role={slot['role']}"
            )

            for i, candidate in enumerate(slot["candidates"], start=1):
                print(f"[{i}] {candidate['title']}")
                print("content_id :", candidate.get("content_id"))

                place = candidate.get("place", {})
                print("overview   :", place.get("overview"))
                print("-" * 40)

        print("=" * 80)

        raw = self._client.complete_json(
            system_prompt=prompts.ITINERARY_REVISION_SYSTEM_PROMPT,
            user_prompt=prompts.build_itinerary_revision_prompt(
                condition.to_llm_dict(),
                existing_itinerary,
                changed_slots,
            ),
        )

        print("=" * 80)
        print("LLM revise raw")
        print(raw)
        print("=" * 80)

        if "days" not in raw:
            raise LLMClientError(
                "itinerary revision response is missing 'days'"
            )

        _validate_itinerary_revision(raw, existing_itinerary, changed_slots)

        return raw


def _validate_generated_itinerary(
    itinerary: dict[str, Any],
    days_with_candidates: list[dict[str, Any]],
) -> None:
    allowed = _candidate_ids_by_slot(days_with_candidates)
    seen: set[int] = set()
    for key, stop in _stops_by_slot(itinerary).items():
        content_id = _content_id(stop)
        if content_id not in allowed.get(key, set()):
            raise LLMClientError(
                f"itinerary generation selected content_id outside slot candidates: {key}"
            )
        if content_id in seen:
            raise LLMClientError(
                f"itinerary generation returned duplicate content_id: {content_id}"
            )
        seen.add(content_id)


def _validate_itinerary_revision(
    itinerary: dict[str, Any],
    existing_itinerary: dict[str, Any],
    changed_slots: list[dict[str, Any]],
) -> None:
    revised = _stops_by_slot(itinerary)
    existing = _stops_by_slot(existing_itinerary)
    changed_keys = {
        (int(slot["day"]), int(slot["sequence"]))
        for slot in changed_slots
    }

    for key in (set(existing) | set(revised)) - changed_keys:
        if revised.get(key) != existing.get(key):
            raise LLMClientError(
                f"itinerary revision changed an unchanged slot: {key}"
            )

    allowed = _candidate_ids_by_slot(
        [{"day": slot["day"], "slots": [slot]} for slot in changed_slots]
    )
    for key in changed_keys:
        stop = revised.get(key)
        if stop is None or _content_id(stop) not in allowed.get(key, set()):
            raise LLMClientError(
                f"itinerary revision selected content_id outside slot candidates: {key}"
            )

    content_ids = [_content_id(stop) for stop in revised.values()]
    if len(content_ids) != len(set(content_ids)):
        raise LLMClientError("itinerary revision returned duplicate content_id")


def _candidate_ids_by_slot(
    days_with_candidates: list[dict[str, Any]],
) -> dict[tuple[int, int], set[int]]:
    allowed: dict[tuple[int, int], set[int]] = {}
    for day in days_with_candidates:
        day_number = int(day["day"])
        for slot in day.get("slots", []):
            key = (day_number, int(slot["sequence"]))
            allowed[key] = {
                int(candidate["content_id"])
                for candidate in slot.get("candidates", [])
            }
    return allowed


def _stops_by_slot(
    itinerary: dict[str, Any],
) -> dict[tuple[int, int], dict[str, Any]]:
    stops: dict[tuple[int, int], dict[str, Any]] = {}
    for day in itinerary.get("days", []):
        day_number = int(day["day"])
        for stop in day.get("stops", []):
            key = (day_number, int(stop["sequence"]))
            if key in stops:
                raise LLMClientError(f"itinerary returned duplicate slot: {key}")
            stops[key] = stop
    return stops


def _content_id(stop: dict[str, Any]) -> int:
    try:
        return int(stop["content_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise LLMClientError("itinerary stop is missing a valid candidate content_id") from exc


def create_llm_service(
    *,
    api_key: str | None = None,
    model: str | None = None,
) -> LLMService:

    api_key = api_key or os.environ.get("OPENAI_API_KEY")

    client = OpenAIChatClient(
        api_key=api_key,
        model=model or os.environ.get(
            "OPENAI_CHAT_MODEL",
            DEFAULT_CHAT_MODEL,
        ),
    )
    

    return LLMService(client)
