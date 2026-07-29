from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from src.common.env import load_env_file

from .aihub_adapter import AIHubRouteAdapter, create_aihub_route_adapter
from .api import create_place_search_service
from .conditions import ConditionExtractionService
from .llm import LLMError, OpenAITravelLLM, TravelLLM
from .models import (
    ItineraryChoice,
    ItineraryDraft,
    RetrievedPlace,
    SlotCandidates,
    SlotRequest,
    TravelConditions,
)
from .retrieval import (
    SlotRetriever,
    add_meal_slots,
    complete_route_slots,
    route_slots,
    select_route_context,
    tourapi_only_slots,
)
from .validation import (
    deterministic_draft,
    max_leg_distance_km,
    validate_and_schedule,
)

PLACES_PER_DAY = 3


class RagOrchestrator:
    """First-pass condition → AIHub route → TourAPI slot RAG chain."""

    def __init__(
        self,
        *,
        condition_service: ConditionExtractionService,
        route_adapter: AIHubRouteAdapter,
        slot_retriever: SlotRetriever,
        llm: TravelLLM,
        repair_attempts: int = 1,
    ) -> None:
        if repair_attempts < 0:
            raise ValueError("repair_attempts must be zero or greater")
        self.condition_service = condition_service
        self.route_adapter = route_adapter
        self.slot_retriever = slot_retriever
        self.llm = llm
        self.repair_attempts = repair_attempts

    def run(
        self,
        *,
        message: str = "",
        history: Sequence[Mapping[str, str]] = (),
        current_conditions: Mapping[str, Any] | TravelConditions | None = None,
        selected_options: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        input_mode = (
            "frontend_selections"
            if selected_options
            else "natural_language"
        )
        if selected_options:
            selected_result = self.condition_service.from_selections(
                selected_options=selected_options,
                current_conditions=current_conditions,
            )
            condition_result = (
                self.condition_service.extract(
                    message=message,
                    history=history,
                    current_conditions=selected_result.conditions,
                )
                if message.strip()
                else selected_result
            )
        else:
            condition_result = self.condition_service.extract(
                message=message,
                history=history,
                current_conditions=current_conditions,
            )
        if not condition_result.ready:
            return {
                "status": "clarification_required",
                **condition_result.to_dict(),
                "meta": {
                    "input_mode": input_mode,
                    "aihub_used": False,
                    "tourapi_rag_used": False,
                    "llm_itinerary_used": False,
                },
            }

        conditions = condition_result.conditions
        route_context = self.route_adapter.build_route_context(conditions)
        patterns = route_context.get("reference_trip_patterns")
        requested_days = int(conditions.duration_days or 0)
        route_strategy = "aihub_pattern"
        aihub_fallback_reason: str | None = None
        if isinstance(patterns, list) and patterns:
            route_context = select_route_context(
                route_context,
                duration_days=requested_days,
                pace=conditions.pace,
                max_leg_distance_km=max_leg_distance_km(conditions),
                places_per_day=PLACES_PER_DAY,
            )
            slots = route_slots(
                route_context,
                duration_days=requested_days,
                max_slots_per_day=PLACES_PER_DAY,
            )
            if not slots:
                route_strategy = "tourapi_only_fallback"
                aihub_fallback_reason = "no_route_slots"
        else:
            slots = ()
            route_strategy = "tourapi_only_fallback"
            aihub_fallback_reason = "no_reference_pattern"

        original_slot_counts = {
            day: len([slot for slot in slots if slot.day == day])
            for day in range(1, requested_days + 1)
        }
        synthesized_days = [
            day
            for day, count in original_slot_counts.items()
            if count != PLACES_PER_DAY
        ]
        if route_strategy == "tourapi_only_fallback":
            slots = tourapi_only_slots(
                conditions,
                places_per_day=PLACES_PER_DAY,
                radius_km=max_leg_distance_km(conditions),
            )
        else:
            slots = complete_route_slots(
                slots,
                conditions,
                places_per_day=PLACES_PER_DAY,
                anchor_radius_km=max_leg_distance_km(conditions),
            )
        synthesized_slot_count = len(
            [
                slot
                for slot in slots
                if slot.template_source
                in {"synthetic_gap_fill", "tourapi_only_fallback"}
            ]
        )
        slots = add_meal_slots(slots, conditions)

        retrieved: list[SlotCandidates] = [
            self.slot_retriever.retrieve(slot, conditions) for slot in slots
        ]
        empty_items = [
            item for item in retrieved if not item.candidates
        ]
        empty_slots = [
            f"Day {item.slot.day} #{item.slot.sequence}"
            for item in empty_items
        ]
        if empty_slots:
            if empty_items and all(
                item.slot.slot_kind == "meal" for item in empty_items
            ):
                return _meal_retrieval_clarification(
                    conditions=conditions,
                    empty_items=empty_items,
                    route_context=route_context,
                    retrieved=retrieved,
                    original_slot_counts=original_slot_counts,
                    synthesized_days=synthesized_days,
                    synthesized_slot_count=synthesized_slot_count,
                    input_mode=input_mode,
                    route_strategy=route_strategy,
                    aihub_fallback_reason=aihub_fallback_reason,
                )
            return {
                "status": "retrieval_incomplete",
                "conditions": conditions.to_dict(),
                "message": (
                    (
                        "AIHub 동선이 없어 생성한 TourAPI 단독 슬롯 중 일부에 "
                        "검증된 후보가 없습니다."
                    )
                    if route_strategy == "tourapi_only_fallback"
                    else (
                        "일부 AIHub 동선 슬롯에 배치할 검증된 TourAPI 후보가 "
                        "없습니다."
                    )
                ),
                "missing_slots": empty_slots,
                "aihub_route_context": _safe_route_context(route_context),
                "slot_candidates": [item.to_dict() for item in retrieved],
                "itinerary": [],
                "meta": {
                    "aihub_used": route_strategy == "aihub_pattern",
                    "tourapi_rag_used": True,
                    "llm_itinerary_used": False,
                    "route_strategy": route_strategy,
                    "aihub_fallback_reason": aihub_fallback_reason,
                    "aihub_original_slot_counts": original_slot_counts,
                    "synthesized_route_days": synthesized_days,
                    "synthesized_slot_count": synthesized_slot_count,
                },
            }

        prompt_context = build_itinerary_prompt_context(
            conditions,
            route_context,
            retrieved,
            frontend_selections=selected_options,
        )
        llm_used = False
        repaired = False
        fallback_used = False
        validation_messages: list[str] = []
        try:
            draft = self.llm.generate_itinerary(prompt_context)
            llm_used = True
            validation = validate_and_schedule(
                draft,
                retrieved,
                conditions,
            )
            attempts = 0
            while not validation.valid and attempts < self.repair_attempts:
                validation_messages = [
                    issue.message for issue in validation.issues
                ]
                draft = self.llm.repair_itinerary(
                    context=prompt_context,
                    invalid_draft=draft,
                    validation_messages=validation_messages,
                )
                repaired = True
                attempts += 1
                validation = validate_and_schedule(
                    draft,
                    retrieved,
                    conditions,
                )
        except (LLMError, ValueError, KeyError, TypeError):
            draft = deterministic_draft(retrieved, conditions)
            validation = validate_and_schedule(
                draft,
                retrieved,
                conditions,
            )
            fallback_used = True

        if not validation.valid:
            validation_messages = [issue.message for issue in validation.issues]
            fallback_draft = deterministic_draft(retrieved, conditions)
            fallback_validation = validate_and_schedule(
                fallback_draft,
                retrieved,
                conditions,
            )
            fallback_used = True
            if fallback_validation.valid:
                draft = fallback_draft
                validation = fallback_validation

        status = "completed" if validation.valid else "validation_failed"
        return {
            "status": status,
            "conditions": conditions.to_dict(),
            "optional_questions": list(condition_result.optional_questions),
            "message": (
                (
                    "AIHub 유사 동선이 없어 TourAPI 장소만으로 일정을 생성했습니다."
                    if route_strategy == "tourapi_only_fallback"
                    else "AIHub 유사 동선 구조에 TourAPI 장소를 배치했습니다."
                )
                if validation.valid
                else "TourAPI 후보 일정이 운영시간·거리 검증을 통과하지 못했습니다."
            ),
            "reference_trip": _selected_pattern_summary(route_context),
            "aihub_route_context": _safe_route_context(route_context),
            "slot_candidates": [item.to_dict() for item in retrieved],
            "draft": draft.to_dict(),
            "itinerary": [stop.to_dict() for stop in validation.schedule],
            "validation": validation.to_dict(),
            "meta": {
                "input_mode": input_mode,
                "places_per_day": PLACES_PER_DAY,
                "tourism_places_per_day": PLACES_PER_DAY,
                "meal_slots_per_day": (
                    3 if conditions.include_breakfast is True else 2
                ),
                "breakfast_included": conditions.include_breakfast is True,
                "menu_preferences": list(conditions.preferred_foods),
                "aihub_used": route_strategy == "aihub_pattern",
                "tourapi_rag_used": True,
                "llm_itinerary_used": llm_used,
                "route_strategy": route_strategy,
                "aihub_fallback_reason": aihub_fallback_reason,
                "llm_repaired": repaired,
                "deterministic_fallback_used": fallback_used,
                "validation_messages_before_fallback": validation_messages,
                "place_source": "tourapi_vector_candidates_only",
                "aihub_tourapi_mapping": "ignored",
                "aihub_original_slot_counts": original_slot_counts,
                "synthesized_route_days": synthesized_days,
                "synthesized_slot_count": synthesized_slot_count,
            },
        }

    def revise(
        self,
        *,
        previous_result: Mapping[str, Any],
        message: str,
    ) -> dict[str, Any]:
        """Replace exactly one requested itinerary stop.

        All unaffected TourAPI content IDs stay fixed. Replacement candidates
        come only from the original slot whitelist and must pass the complete
        deterministic validator before being returned.
        """

        edit = _parse_replacement_request(message)
        if edit is None:
            return _revision_clarification(
                previous_result,
                "수정할 일차와 기존 장소명을 함께 알려주세요. "
                "예: '2일차의 우도를 다른 장소로 교체해 주세요.'",
            )
        day, requested_title = edit
        itinerary = previous_result.get("itinerary")
        if not isinstance(itinerary, list) or not itinerary:
            return _revision_unavailable(
                previous_result,
                "수정할 기존 일정이 없습니다.",
            )
        matches = [
            stop
            for stop in itinerary
            if isinstance(stop, Mapping)
            and int(stop.get("day") or 0) == day
            and _title_matches(
                str(stop.get("title") or ""),
                requested_title,
            )
        ]
        if len(matches) != 1:
            day_titles = [
                str(stop.get("title") or "")
                for stop in itinerary
                if isinstance(stop, Mapping)
                and int(stop.get("day") or 0) == day
            ]
            detail = (
                f"Day {day}에서 '{requested_title}'을 정확히 한 곳으로 "
                f"확정하지 못했습니다. 현재 장소: {', '.join(day_titles)}"
            )
            return _revision_clarification(previous_result, detail)

        target = matches[0]
        target_sequence = int(target.get("sequence") or 0)
        target_content_id = int(target.get("content_id") or 0)
        slot_candidates = _restore_slot_candidates(
            previous_result.get("slot_candidates")
        )
        target_slot = next(
            (
                item
                for item in slot_candidates
                if item.slot.day == day
                and item.slot.sequence == target_sequence
            ),
            None,
        )
        if target_slot is None:
            return _revision_unavailable(
                previous_result,
                "기존 결과에 해당 슬롯의 TourAPI 화이트리스트가 없습니다.",
            )

        conditions = _conditions_after_replacement(
            TravelConditions.from_mapping(previous_result.get("conditions")),
            day=day,
            replaced_title=str(target.get("title") or requested_title),
        )
        original_choices = _choices_from_itinerary(itinerary)
        used_ids = {
            choice.content_id
            for choice in original_choices
            if choice.content_id != target_content_id
        }
        alternatives = [
            place
            for place in target_slot.candidates
            if place.content_id != target_content_id
            and place.content_id not in used_ids
            and not _title_matches(place.title, requested_title)
        ]
        attempted_issues: list[dict[str, Any]] = []
        for alternative in alternatives:
            replacement = ItineraryChoice(
                day=day,
                slot_sequence=target_sequence,
                content_id=alternative.content_id,
                stay_minutes=int(target.get("stay_minutes") or 60),
                reason=(
                    f"사용자 요청에 따라 {target.get('title')}을(를) "
                    "같은 슬롯의 검증된 TourAPI 후보로 교체했습니다."
                ),
            )
            choices = tuple(
                replacement
                if choice.day == day
                and choice.slot_sequence == target_sequence
                else choice
                for choice in original_choices
            )
            draft = ItineraryDraft(choices)
            validation = validate_and_schedule(
                draft,
                slot_candidates,
                conditions,
            )
            if validation.valid:
                updated = dict(previous_result)
                updated.update(
                    {
                        "status": "completed",
                        "conditions": conditions.to_dict(),
                        "message": (
                            f"Day {day}의 {target.get('title')}만 "
                            f"{alternative.title}(으)로 교체했습니다."
                        ),
                        "draft": draft.to_dict(),
                        "itinerary": [
                            stop.to_dict() for stop in validation.schedule
                        ],
                        "validation": validation.to_dict(),
                    }
                )
                updated["meta"] = {
                    **dict(previous_result.get("meta") or {}),
                    "edit_mode": "targeted_replacement",
                    "edited_day": day,
                    "edited_sequence": target_sequence,
                    "replaced_content_id": target_content_id,
                    "replacement_content_id": alternative.content_id,
                    "unchanged_place_count": len(choices) - 1,
                }
                return updated
            attempted_issues.extend(
                issue.to_dict() for issue in validation.issues
            )

        unavailable = _revision_unavailable(
            previous_result,
            f"Day {day}의 {target.get('title')}을 대체할 검증 통과 후보가 없습니다.",
        )
        unavailable["attempted_validation_issues"] = attempted_issues
        return unavailable


def _meal_retrieval_clarification(
    *,
    conditions: TravelConditions,
    empty_items: Sequence[SlotCandidates],
    route_context: Mapping[str, Any],
    retrieved: Sequence[SlotCandidates],
    original_slot_counts: Mapping[int, int],
    synthesized_days: Sequence[int],
    synthesized_slot_count: int,
    input_mode: str,
    route_strategy: str,
    aihub_fallback_reason: str | None,
) -> dict[str, Any]:
    meal_labels = {
        "breakfast": "아침",
        "lunch": "점심",
        "dinner": "저녁",
    }
    current_radius = float(conditions.meal_search_radius_km or 8.0)
    missing_details = [
        {
            "day": item.slot.day,
            "meal_type": item.slot.meal_type,
            "meal_label": meal_labels.get(
                item.slot.meal_type or "",
                "식사",
            ),
            "search_radius_km": item.slot.radius_km,
        }
        for item in empty_items
    ]
    missing_text = ", ".join(
        f"{detail['day']}일차 {detail['meal_label']}"
        for detail in missing_details
    )
    suggested_radii = [
        radius for radius in (12, 20, 30) if radius > current_radius
    ][:2]
    options = [
        {
            "value": f"expand_meal_radius_{radius}",
            "label": f"{radius}km까지 검색",
            "description": (
                f"식당 검색 반경을 {radius}km로 넓혀 다시 검색합니다."
            ),
            "selected_options": {
                "meal_search_radius_km": radius,
            },
        }
        for radius in suggested_radii
    ]
    options.append(
        {
            "value": "skip_unavailable_meals",
            "label": "해당 식사 일정 제외",
            "description": (
                "찾지 못한 식사 슬롯만 일정에서 제외하고 관광 일정을 계속합니다."
            ),
            "selected_options": {
                "skipped_meals": [
                    {
                        "day": detail["day"],
                        "meal_type": detail["meal_type"],
                    }
                    for detail in missing_details
                ],
            },
        }
    )
    options.append(
        {
            "value": "enter_meal_preference",
            "label": "메뉴·지역 직접 입력",
            "description": (
                "원하는 음식이나 식사할 지역을 자연어로 입력합니다."
            ),
            "selected_options": {},
        }
    )
    question = (
        f"{missing_text} 식당을 현재 검색 반경 "
        f"{current_radius:g}km 안에서 찾지 못했습니다. "
        "검색 반경을 넓힐까요, 해당 식사 일정을 제외할까요, "
        "아니면 원하는 메뉴·지역을 직접 입력하시겠습니까?"
    )
    return {
        "status": "clarification_required",
        "ready": False,
        "clarification_kind": "meal_candidate_unavailable",
        "conditions": conditions.to_dict(),
        "message": question,
        "clarification_questions": [question],
        "clarification_options": options,
        "missing_meal_slots": missing_details,
        "missing_slots": [
            f"Day {item.slot.day} #{item.slot.sequence}"
            for item in empty_items
        ],
        "aihub_route_context": _safe_route_context(route_context),
        "slot_candidates": [item.to_dict() for item in retrieved],
        "itinerary": [],
        "meta": {
            "input_mode": input_mode,
            "aihub_used": route_strategy == "aihub_pattern",
            "tourapi_rag_used": True,
            "llm_itinerary_used": False,
            "route_strategy": route_strategy,
            "aihub_fallback_reason": aihub_fallback_reason,
            "aihub_original_slot_counts": dict(original_slot_counts),
            "synthesized_route_days": list(synthesized_days),
            "synthesized_slot_count": synthesized_slot_count,
            "meal_search_radius_km": current_radius,
        },
    }


def _parse_replacement_request(message: str) -> tuple[int, str] | None:
    normalized = message.strip()
    if not normalized:
        return None
    pattern = re.compile(
        r"(?P<day>\d+)\s*일차(?:의|에|에서)?\s*"
        r"(?P<title>.+?)(?:을|를)\s*"
        r"(?:다른\s*(?:것|걸|장소)(?:으?로)?\s*)?"
        r"(?:교체|변경|바꿔|바꾸)",
    )
    match = pattern.search(normalized)
    if match is None:
        return None
    day = int(match.group("day"))
    title = match.group("title").strip(" ,.")
    if day <= 0 or not title:
        return None
    return day, title


def _restore_slot_candidates(value: Any) -> tuple[SlotCandidates, ...]:
    if not isinstance(value, list):
        return ()
    restored: list[SlotCandidates] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        raw_slot = item.get("slot")
        if not isinstance(raw_slot, Mapping):
            continue
        try:
            slot = SlotRequest(
                day=int(raw_slot.get("day") or 0),
                sequence=int(raw_slot.get("sequence") or 0),
                role=str(raw_slot.get("role") or "visit"),
                category=str(raw_slot.get("category") or "unknown"),
                target_collections=tuple(
                    str(entry)
                    for entry in raw_slot.get("target_collections") or ()
                ),
                itinerary_roles=tuple(
                    str(entry)
                    for entry in raw_slot.get("itinerary_roles") or ()
                ),
                stay_minutes=_optional_int(raw_slot.get("stay_minutes")),
                latitude=_optional_float(raw_slot.get("latitude")),
                longitude=_optional_float(raw_slot.get("longitude")),
                radius_km=_optional_float(raw_slot.get("radius_km")),
                template_source=str(
                    raw_slot.get("template_source") or "aihub"
                ),
                route_anchor=_optional_text(raw_slot.get("route_anchor")),
                slot_kind=str(raw_slot.get("slot_kind") or "tourism"),
                meal_type=_optional_text(raw_slot.get("meal_type")),
            )
        except (TypeError, ValueError):
            continue
        candidates = tuple(
            place
            for raw_place in item.get("candidates") or ()
            if (place := _restore_place(raw_place)) is not None
        )
        restored.append(
            SlotCandidates(
                slot=slot,
                query=str(item.get("query") or ""),
                candidates=candidates,
            )
        )
    return tuple(restored)


def _restore_place(value: Any) -> RetrievedPlace | None:
    if not isinstance(value, Mapping):
        return None
    try:
        return RetrievedPlace(
            content_id=int(value.get("content_id") or 0),
            title=str(value.get("title") or ""),
            latitude=float(value.get("latitude") or 0.0),
            longitude=float(value.get("longitude") or 0.0),
            similarity_score=float(value.get("similarity_score") or 0.0),
            rank=int(value.get("rank") or 0),
            dataset=str(value.get("dataset") or ""),
            target_collection=str(value.get("target_collection") or ""),
            itinerary_role=str(value.get("itinerary_role") or ""),
            tags=tuple(str(entry) for entry in value.get("tags") or ()),
            address=str(value.get("address") or ""),
            opening_hours=str(value.get("opening_hours") or ""),
            closed_days=str(value.get("closed_days") or ""),
            parking=str(value.get("parking") or ""),
            reservation=str(value.get("reservation") or ""),
            use_fee=str(value.get("use_fee") or ""),
            rating=_optional_float(value.get("rating")),
            rating_count=_optional_int(value.get("rating_count")),
            overview=str(value.get("overview") or ""),
            route_eligible=bool(value.get("route_eligible", True)),
            schedule_eligible=bool(value.get("schedule_eligible", True)),
            requires_verification=bool(
                value.get("requires_verification", False)
            ),
            distance_km=_optional_float(value.get("distance_km")),
            slot_score=_optional_float(value.get("slot_score")),
            score_breakdown=dict(value.get("score_breakdown") or {}),
            raw=dict(value.get("raw") or {}),
        )
    except (TypeError, ValueError):
        return None


def _choices_from_itinerary(
    itinerary: Sequence[Mapping[str, Any]],
) -> tuple[ItineraryChoice, ...]:
    return tuple(
        ItineraryChoice(
            day=int(stop.get("day") or 0),
            slot_sequence=int(stop.get("sequence") or 0),
            content_id=int(stop.get("content_id") or 0),
            stay_minutes=int(stop.get("stay_minutes") or 60),
            reason=str(stop.get("reason") or "기존 일정 선택을 유지합니다."),
        )
        for stop in itinerary
        if isinstance(stop, Mapping)
    )


def _conditions_after_replacement(
    conditions: TravelConditions,
    *,
    day: int,
    replaced_title: str,
) -> TravelConditions:
    replaced_key = _normalized_title(replaced_title)
    payload = conditions.to_dict()
    payload["must_visit_places"] = [
        name
        for name in conditions.must_visit_places
        if not _title_keys_match(_normalized_title(name), replaced_key)
    ]
    required_by_day: list[dict[str, Any]] = []
    for requirement in conditions.required_day_itineraries:
        names = [
            name
            for name in requirement.place_names
            if not (
                requirement.day == day
                and _title_keys_match(
                    _normalized_title(name),
                    replaced_key,
                )
            )
        ]
        if names:
            required_by_day.append(
                {"day": requirement.day, "place_names": names}
            )
    payload["required_day_itineraries"] = required_by_day
    return TravelConditions.from_mapping(payload)


def _revision_clarification(
    previous_result: Mapping[str, Any],
    question: str,
) -> dict[str, Any]:
    return {
        "status": "clarification_required",
        "conditions": dict(previous_result.get("conditions") or {}),
        "clarification_questions": [question],
        "itinerary": list(previous_result.get("itinerary") or []),
        "meta": {
            **dict(previous_result.get("meta") or {}),
            "edit_mode": "targeted_replacement",
            "itinerary_preserved": True,
        },
    }


def _revision_unavailable(
    previous_result: Mapping[str, Any],
    message: str,
) -> dict[str, Any]:
    return {
        **dict(previous_result),
        "status": "replacement_unavailable",
        "message": message,
        "itinerary": list(previous_result.get("itinerary") or []),
        "meta": {
            **dict(previous_result.get("meta") or {}),
            "edit_mode": "targeted_replacement",
            "itinerary_preserved": True,
        },
    }


def _title_matches(first: str, second: str) -> bool:
    return _title_keys_match(
        _normalized_title(first),
        _normalized_title(second),
    )


def _title_keys_match(first: str, second: str) -> bool:
    return bool(first and second and (first in second or second in first))


def _normalized_title(value: str) -> str:
    return "".join(
        character.lower() for character in value if character.isalnum()
    )


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    try:
        return None if value in (None, "") else int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def build_itinerary_prompt_context(
    conditions: TravelConditions,
    route_context: Mapping[str, Any],
    slot_candidates: Sequence[SlotCandidates],
    *,
    frontend_selections: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    pattern = _selected_pattern(route_context)
    route_strategy = (
        "aihub_pattern"
        if pattern
        else "tourapi_only_fallback"
    )
    slots_payload: list[dict[str, Any]] = []
    for item in slot_candidates:
        candidates = [
            {
                "content_id": place.content_id,
                "title": place.title,
                "target_collection": place.target_collection,
                "itinerary_role": place.itinerary_role,
                "tags": list(place.tags),
                "address": place.address,
                "latitude": place.latitude,
                "longitude": place.longitude,
                "opening_hours": place.opening_hours,
                "closed_days": place.closed_days,
                "parking": place.parking,
                "rating": place.rating,
                "rating_count": place.rating_count,
                "distance_km": place.distance_km,
                "semantic_similarity": place.similarity_score,
                "slot_score": place.slot_score,
                "score_breakdown": dict(place.score_breakdown),
                "overview": place.overview[:800],
            }
            for place in item.candidates
        ]
        slots_payload.append(
            {
                "day": item.slot.day,
                "slot_sequence": item.slot.sequence,
                "role": item.slot.role,
                "category": item.slot.category,
                "slot_kind": item.slot.slot_kind,
                "meal_type": item.slot.meal_type,
                "suggested_stay_minutes": item.slot.stay_minutes,
                "template_source": item.slot.template_source,
                "route_anchor": item.slot.route_anchor,
                "location_hint": {
                    "latitude": item.slot.latitude,
                    "longitude": item.slot.longitude,
                    "radius_km": item.slot.radius_km,
                },
                "allowed_content_ids": [
                    place["content_id"] for place in candidates
                ],
                "tourapi_candidates": candidates,
            }
        )
    return {
        "input_mode": (
            "frontend_selections"
            if frontend_selections
            else "natural_language"
        ),
        "frontend_selections": dict(frontend_selections or {}),
        "user_conditions": conditions.to_dict(),
        "aihub_reference_pattern": pattern,
        "slots": slots_payload,
        "policy": {
            "source_priority": (
                [
                    "user_conditions",
                    "tourapi_verified_facts",
                    "distance_and_opening_hours",
                    "aihub_route_pattern",
                ]
                if pattern
                else [
                    "user_conditions",
                    "tourapi_verified_facts",
                    "distance_and_opening_hours",
                ]
            ),
            "route_strategy": route_strategy,
            "aihub_route_pattern_available": bool(pattern),
            "place_source": "TourAPI candidates only",
            "aihub_place_names_allowed": False,
            "one_place_per_slot": True,
            "tourism_places_per_day": PLACES_PER_DAY,
            "meal_slots_per_day": (
                3 if conditions.include_breakfast is True else 2
            ),
            "every_slot_required": True,
            "duplicate_content_ids_allowed": False,
            "max_leg_distance_km": max_leg_distance_km(conditions),
            "schedule_windows": {
                "breakfast": (
                    "07:30-09:00"
                    if conditions.include_breakfast is True
                    else "not included unless explicitly requested"
                ),
                "slot_1": "09:00-12:00",
                "lunch": "12:00-13:00",
                "slot_2": "13:00-15:30",
                "slot_3": "15:30-18:00",
                "dinner": "18:00-19:30",
            },
            "food_and_cafe_as_tourism_places": False,
            "restaurants_allowed_only_in_meal_slots": True,
            "restaurant_ranking": [
                "distance",
                "verified_rating_when_available",
                "preferred_menu_match",
                "opening_hours",
            ],
            "unknown_rating_policy": "neutral; never fabricate a rating",
            "route_anchors": {
                "start_point": conditions.entry_point,
                "end_point": conditions.exit_point,
                "accommodation": conditions.accommodation_address,
            },
            "conditional_time_constraints": {
                "trip_start_time": conditions.arrival_time,
                "departure_airport": conditions.exit_point,
                "airport_arrival_deadline": conditions.departure_time,
            },
            "route_anchors_are_optional": True,
            "route_anchor_distance_requires_coordinates": True,
        },
    }


def create_rag_orchestrator(
    *,
    project_root: str | Path | None = None,
    env_file: str | Path | None = None,
) -> RagOrchestrator:
    root = Path(project_root or Path.cwd())
    resolved_env = Path(env_file) if env_file else root / ".env"
    if resolved_env.exists():
        load_env_file(resolved_env)
    llm = OpenAITravelLLM()
    condition_service = ConditionExtractionService(llm)
    route_adapter = create_aihub_route_adapter(
        env_file=resolved_env,
        top_k=30,
    )
    place_service = create_place_search_service(
        project_root=root,
        env_file=resolved_env,
    )
    return RagOrchestrator(
        condition_service=condition_service,
        route_adapter=route_adapter,
        slot_retriever=SlotRetriever(place_service),
        llm=llm,
    )


def _selected_pattern(route_context: Mapping[str, Any]) -> dict[str, Any]:
    patterns = route_context.get("reference_trip_patterns")
    if isinstance(patterns, list) and patterns and isinstance(patterns[0], Mapping):
        return dict(patterns[0])
    return {}


def _selected_pattern_summary(
    route_context: Mapping[str, Any],
) -> dict[str, Any]:
    pattern = _selected_pattern(route_context)
    return {
        key: pattern.get(key)
        for key in (
            "reference_trip_id",
            "match_score",
            "match_confidence",
            "matched_on",
            "conflicts",
            "profile",
        )
    }


def _safe_route_context(
    route_context: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the already-sanitized AIHub context without raw route rows."""

    return {
        "user_constraints": route_context.get("user_constraints", {}),
        "reference_trip_patterns": route_context.get(
            "reference_trip_patterns",
            [],
        ),
        "context_policy": route_context.get("context_policy", {}),
    }
