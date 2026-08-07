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
    def generate_style_query(self, condition: TravelCondition) -> str:
        """Build a single broad query for the RAG candidate-pool step.

        Unlike :meth:`generate_search_query`, this is not tied to a single
        slot's role. It is used once per itinerary to gather a wide pool of
        candidates driven purely by the user's style (``preferred_visit_types``)
        and free-text wishes (``must_visit_places``), matching the "RAG"
        branch of the AIHub/RAG retrieval pipeline.
        """

        raw = self._client.complete_json(
            system_prompt=prompts.STYLE_QUERY_GENERATION_SYSTEM_PROMPT,
            user_prompt=prompts.build_style_query_generation_prompt(
                condition.to_llm_dict(),
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

        if "days" not in raw:
            raise LLMClientError(
                "itinerary revision response is missing 'days'"
            )

        return raw


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