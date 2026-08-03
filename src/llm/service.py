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
    # 4. Final Itinerary Generation
    # ------------------------------------------------------------------
    def generate_itinerary(
        self,
        condition: TravelCondition,
        days_with_candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:

        raw = self._client.complete_json(
            system_prompt=prompts.ITINERARY_GENERATION_SYSTEM_PROMPT,
            user_prompt=prompts.build_itinerary_generation_prompt(
                condition.to_llm_dict(),
                days_with_candidates,
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