from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .llm import TravelLLM
from .models import TravelConditions


CLARIFICATION_QUESTIONS = {
    "duration_days": "제주에서 며칠 동안 여행하시나요?",
    "party_type": (
        "누구와 여행하시나요? 혼자, 친구·연인, 가족, 자녀 동반, "
        "부모님 동반 중에서 알려주세요."
    ),
    "local_transport": (
        "제주에서는 어떤 교통수단을 이용하시나요? "
        "렌터카, 자가용, 대중교통, 택시 중에서 알려주세요."
    ),
    "preferred_visit_types": (
        "어떤 유형의 장소를 선호하시나요? 자연, 역사, 문화, 시장·쇼핑, "
        "레저, 테마파크, 트레일, 축제, 음식·카페, 체험 중에서 알려주세요."
    ),
    "departure_airport": (
        "마지막 날 제한시각까지 도착해야 하는 공항은 어디인가요?"
    ),
}


@dataclass(frozen=True)
class ConditionResult:
    conditions: TravelConditions
    clarification_questions: tuple[str, ...]
    optional_questions: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return not self.clarification_questions

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "conditions": self.conditions.to_dict(),
            "clarification_questions": list(self.clarification_questions),
            "optional_questions": list(self.optional_questions),
        }


class ConditionExtractionService:
    def __init__(self, llm: TravelLLM) -> None:
        self.llm = llm

    def extract(
        self,
        *,
        message: str,
        history: Sequence[Mapping[str, str]] = (),
        current_conditions: Mapping[str, Any] | TravelConditions | None = None,
    ) -> ConditionResult:
        if not message.strip():
            raise ValueError("message must not be blank")
        if isinstance(current_conditions, TravelConditions):
            current = current_conditions
        else:
            current = TravelConditions.from_mapping(current_conditions)

        extracted = self.llm.extract_conditions(
            message=message,
            history=history,
            current_conditions=current.to_dict(),
        )
        merged = _resolve_condition_conflicts(current.merged_with(extracted))
        questions = _clarification_questions(merged)
        return ConditionResult(merged, questions, _optional_questions(merged))

    def from_selections(
        self,
        *,
        selected_options: Mapping[str, Any],
        current_conditions: Mapping[str, Any] | TravelConditions | None = None,
    ) -> ConditionResult:
        """Trust canonical frontend selections without spending an LLM call."""

        if isinstance(current_conditions, TravelConditions):
            current = current_conditions
        else:
            current = TravelConditions.from_mapping(current_conditions)
        selected = TravelConditions.from_mapping(selected_options)
        merged = _resolve_condition_conflicts(current.merged_with(selected))
        questions = _clarification_questions(merged)
        return ConditionResult(merged, questions, _optional_questions(merged))


def _clarification_questions(
    conditions: TravelConditions,
) -> tuple[str, ...]:
    fields = (
        *conditions.missing_required_fields(),
        *conditions.missing_conditional_fields(),
    )
    return tuple(CLARIFICATION_QUESTIONS[field] for field in fields)


def _optional_questions(
    conditions: TravelConditions,
) -> tuple[str, ...]:
    if conditions.preferred_foods:
        return ()
    return (
        "식당 추천에 반영할 원하는 메뉴가 있나요? "
        "예: 제주 흑돼지, 갈치조림, 해산물. 없으면 '상관없음'이라고 답해주세요.",
    )


def _resolve_condition_conflicts(
    conditions: TravelConditions,
) -> TravelConditions:
    day_required_keys = {
        _normalized(name)
        for item in conditions.required_day_itineraries
        for name in item.place_names
    }
    required_keys = {
        _normalized(value)
        for value in (
            *conditions.must_visit_places,
            *(
                name
                for item in conditions.required_day_itineraries
                for name in item.place_names
            ),
        )
    }
    excluded_place_keys = {
        _normalized(value) for value in conditions.excluded_places
    }
    excluded_food_keys = {
        _normalized(value) for value in conditions.excluded_foods
    }
    excluded = tuple(
        value
        for value in conditions.excluded_places
        if _normalized(value) not in required_keys
    )
    payload = conditions.to_dict()
    payload["must_visit_places"] = [
        value
        for value in conditions.must_visit_places
        if _normalized(value) not in day_required_keys
    ]
    payload["excluded_places"] = list(excluded)
    payload["preferred_places"] = [
        value
        for value in conditions.preferred_places
        if _normalized(value) not in excluded_place_keys
    ]
    payload["preferred_foods"] = [
        value
        for value in conditions.preferred_foods
        if _normalized(value) not in excluded_food_keys
    ]
    return TravelConditions.from_mapping(payload)


def _normalized(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())
