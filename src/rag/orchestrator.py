from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from src.common.env import load_env_file

from .aihub_adapter import AIHubRouteAdapter, create_aihub_route_adapter
from .api import create_place_search_service
from .conditions import ConditionExtractionService
from .llm import LLMError, OpenAITravelLLM, TravelLLM
from .models import SlotCandidates, TravelConditions
from .retrieval import (
    SlotRetriever,
    complete_route_slots,
    route_slots,
    select_route_context,
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
        route_context = select_route_context(
            route_context,
            duration_days=int(conditions.duration_days or 0),
            pace=conditions.pace,
            max_leg_distance_km=max_leg_distance_km(conditions),
            places_per_day=PLACES_PER_DAY,
        )
        patterns = route_context.get("reference_trip_patterns")
        if not isinstance(patterns, list) or not patterns:
            return {
                "status": "no_reference_pattern",
                "conditions": conditions.to_dict(),
                "message": "사용자 조건과 비교할 AIHub 여행 동선을 찾지 못했습니다.",
                "aihub_route_context": route_context,
                "slot_candidates": [],
                "itinerary": [],
                "meta": {
                    "aihub_used": False,
                    "tourapi_rag_used": False,
                    "llm_itinerary_used": False,
                },
            }

        slots = route_slots(
            route_context,
            duration_days=int(conditions.duration_days or 0),
            max_slots_per_day=PLACES_PER_DAY,
        )
        if not slots:
            return {
                "status": "no_route_slots",
                "conditions": conditions.to_dict(),
                "message": "AIHub 유사 여행에서 사용할 수 있는 동선 슬롯이 없습니다.",
                "aihub_route_context": route_context,
                "slot_candidates": [],
                "itinerary": [],
                "meta": {
                    "aihub_used": True,
                    "tourapi_rag_used": False,
                    "llm_itinerary_used": False,
                },
            }

        requested_days = int(conditions.duration_days or 0)
        original_slot_counts = {
            day: len([slot for slot in slots if slot.day == day])
            for day in range(1, requested_days + 1)
        }
        synthesized_days = [
            day
            for day, count in original_slot_counts.items()
            if count != PLACES_PER_DAY
        ]
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
                if slot.template_source == "synthetic_gap_fill"
            ]
        )

        retrieved: list[SlotCandidates] = [
            self.slot_retriever.retrieve(slot, conditions) for slot in slots
        ]
        empty_slots = [
            f"Day {item.slot.day} #{item.slot.sequence}"
            for item in retrieved
            if not item.candidates
        ]
        if empty_slots:
            return {
                "status": "retrieval_incomplete",
                "conditions": conditions.to_dict(),
                "message": (
                    "일부 AIHub 동선 슬롯에 배치할 검증된 TourAPI 후보가 "
                    "없습니다."
                ),
                "missing_slots": empty_slots,
                "aihub_route_context": _safe_route_context(route_context),
                "slot_candidates": [item.to_dict() for item in retrieved],
                "itinerary": [],
                "meta": {
                    "aihub_used": True,
                    "tourapi_rag_used": True,
                    "llm_itinerary_used": False,
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
            "message": (
                "AIHub 유사 동선 구조에 TourAPI 장소를 배치했습니다."
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
                "aihub_used": True,
                "tourapi_rag_used": True,
                "llm_itinerary_used": llm_used,
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


def build_itinerary_prompt_context(
    conditions: TravelConditions,
    route_context: Mapping[str, Any],
    slot_candidates: Sequence[SlotCandidates],
    *,
    frontend_selections: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    pattern = _selected_pattern(route_context)
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
            "source_priority": [
                "user_conditions",
                "tourapi_verified_facts",
                "distance_and_opening_hours",
                "aihub_route_pattern",
            ],
            "place_source": "TourAPI candidates only",
            "aihub_place_names_allowed": False,
            "one_place_per_slot": True,
            "places_per_day": PLACES_PER_DAY,
            "every_slot_required": True,
            "duplicate_content_ids_allowed": False,
            "max_leg_distance_km": max_leg_distance_km(conditions),
            "route_anchors": {
                "start_point": conditions.entry_point,
                "end_point": conditions.exit_point,
                "accommodation": conditions.accommodation_address,
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
