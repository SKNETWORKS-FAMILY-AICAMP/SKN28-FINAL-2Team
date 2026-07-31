from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import logging
import os
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
from .operations import (
    HolidayCalendar,
    PlaceOperationalFactsProvider,
    create_operational_services_from_env,
)
from .retrieval import (
    SlotRetriever,
    add_meal_slots,
    complete_route_slots,
    PACE_SLOTS_PER_DAY,
    route_slots,
    select_route_context,
    tourapi_only_slots,
)
from .routing import (
    HaversineRouteMetricsProvider,
    RouteMetricsProvider,
    RouteProviderError,
    create_route_metrics_provider_from_env,
)
from .validation import (
    ValidationPolicy,
    deterministic_draft,
    max_leg_distance_km,
    place_coordinates,
    resolve_day_end_anchor,
    resolve_day_start_anchor,
    validate_and_schedule,
)

PLACES_PER_DAY = 3
MAX_TOURISM_PLACES_PER_DAY = 8
LOGGER = logging.getLogger(__name__)


class RagOrchestrator:
    """First-pass condition → AIHub route → TourAPI slot RAG chain."""

    def __init__(
        self,
        *,
        condition_service: ConditionExtractionService,
        route_adapter: AIHubRouteAdapter,
        slot_retriever: SlotRetriever,
        llm: TravelLLM,
        route_provider: RouteMetricsProvider | None = None,
        validation_policy: ValidationPolicy | None = None,
        operational_provider: PlaceOperationalFactsProvider | None = None,
        holiday_calendar: HolidayCalendar | None = None,
        repair_attempts: int = 1,
    ) -> None:
        if repair_attempts < 0:
            raise ValueError("repair_attempts must be zero or greater")
        self.condition_service = condition_service
        self.route_adapter = route_adapter
        self.slot_retriever = slot_retriever
        self.llm = llm
        self.route_provider = route_provider or HaversineRouteMetricsProvider()
        self.validation_policy = validation_policy or ValidationPolicy()
        self.operational_provider = operational_provider
        self.holiday_calendar = holiday_calendar
        self.repair_attempts = repair_attempts

    def run(
        self,
        *,
        message: str = "",
        history: Sequence[Mapping[str, str]] = (),
        current_conditions: Mapping[str, Any] | TravelConditions | None = None,
        selected_options: Mapping[str, Any] | None = None,
        avoid_content_ids: Sequence[int] = (),
        tourism_places_by_day: Mapping[int, int] | None = None,
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
        places_per_day = PLACES_PER_DAY
        requested_days = int(conditions.duration_days or 0)
        target_places_by_day = _resolve_tourism_places_by_day(
            duration_days=requested_days,
            overrides=tourism_places_by_day,
        )
        max_places_per_day = max(
            target_places_by_day.values(),
            default=places_per_day,
        )
        route_context = self.route_adapter.build_route_context(conditions)
        patterns = route_context.get("reference_trip_patterns")
        route_strategy = "aihub_pattern"
        aihub_fallback_reason: str | None = None
        if isinstance(patterns, list) and patterns:
            route_context = select_route_context(
                route_context,
                duration_days=requested_days,
                pace=conditions.pace,
                max_leg_distance_km=max_leg_distance_km(conditions),
                places_per_day=max_places_per_day,
            )
            slots = route_slots(
                route_context,
                duration_days=requested_days,
                max_slots_per_day=max_places_per_day,
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
            if count != target_places_by_day[day]
        ]
        if route_strategy == "tourapi_only_fallback":
            slots = tourapi_only_slots(
                conditions,
                places_per_day=places_per_day,
                radius_km=max_leg_distance_km(conditions),
                places_per_day_by_day=target_places_by_day,
            )
        else:
            slots = complete_route_slots(
                slots,
                conditions,
                places_per_day=places_per_day,
                anchor_radius_km=max_leg_distance_km(conditions),
                places_per_day_by_day=target_places_by_day,
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

        tourism_slots = [
            slot for slot in slots if slot.slot_kind != "meal"
        ]
        meal_slots = [
            slot for slot in slots if slot.slot_kind == "meal"
        ]
        tourism_retrieved = [
            self.slot_retriever.retrieve(slot, conditions)
            for slot in tourism_slots
        ]
        broad_fallback_slots = {
            (slot.day, slot.sequence): slot
            for slot in tourapi_only_slots(
                conditions,
                places_per_day=places_per_day,
                radius_km=max_leg_distance_km(conditions),
                places_per_day_by_day=target_places_by_day,
            )
        }
        tourism_retrieved = [
            (
                self.slot_retriever.retrieve(
                    broad_fallback_slots[
                        (item.slot.day, item.slot.sequence)
                    ],
                    conditions,
                )
                if not item.candidates
                else item
            )
            for item in tourism_retrieved
        ]
        avoided_ids = {int(value) for value in avoid_content_ids}
        tourism_retrieved = _filter_avoided_candidates(
            tourism_retrieved,
            avoided_ids,
        )
        tourism_draft = deterministic_draft(
            tourism_retrieved,
            conditions,
        )
        selected_tourism = _selected_places_by_slot(
            tourism_draft,
            tourism_retrieved,
        )
        locked_tourism = [
            replace(
                item,
                candidates=(
                    (selected_tourism[key],)
                    if (
                        key := (item.slot.day, item.slot.sequence)
                    ) in selected_tourism
                    else item.candidates
                ),
            )
            for item in tourism_retrieved
        ]
        anchored_meal_slots = [
            _anchor_meal_slot_to_selected_tourism(
                slot,
                selected_tourism,
                places_per_day=target_places_by_day[slot.day],
            )
            for slot in meal_slots
        ]
        meal_retrieved = [
            self.slot_retriever.retrieve(slot, conditions)
            for slot in anchored_meal_slots
        ]
        meal_retrieved = _filter_avoided_candidates(
            meal_retrieved,
            avoided_ids,
        )
        retrieved: list[SlotCandidates] = sorted(
            [*locked_tourism, *meal_retrieved],
            key=lambda item: (item.slot.day, item.slot.sequence),
        )
        revision_retrieved: list[SlotCandidates] = sorted(
            [*tourism_retrieved, *meal_retrieved],
            key=lambda item: (item.slot.day, item.slot.sequence),
        )
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
                tourism_validation = validate_and_schedule(
                    tourism_draft,
                    locked_tourism,
                    conditions,
                    route_provider=self.route_provider,
                    policy=self.validation_policy,
                    operational_provider=self.operational_provider,
                    holiday_calendar=self.holiday_calendar,
                )
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
                    tourism_places_by_day=target_places_by_day,
                    provisional_itinerary=[
                        stop.to_dict()
                        for stop in tourism_validation.schedule
                    ],
                    provisional_validation=tourism_validation.to_dict(),
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
                    "tourism_places_per_day": places_per_day,
                    "tourism_places_by_day": target_places_by_day,
                },
            }

        prompt_context = build_itinerary_prompt_context(
            conditions,
            route_context,
            retrieved,
            frontend_selections=selected_options,
            tourism_places_by_day=target_places_by_day,
        )
        llm_used = False
        repaired = False
        fallback_used = False
        candidate_retry_used = False
        candidate_retry_count = 0
        validation_messages: list[str] = []
        try:
            draft = self.llm.generate_itinerary(prompt_context)
            llm_used = True
            validation = validate_and_schedule(
                draft,
                retrieved,
                conditions,
                route_provider=self.route_provider,
                policy=self.validation_policy,
                operational_provider=self.operational_provider,
                holiday_calendar=self.holiday_calendar,
            )
        except LLMError:
            LOGGER.warning(
                "LLM itinerary generation failed; using deterministic optimizer",
                exc_info=True,
            )
            draft = deterministic_draft(revision_retrieved, conditions)
            validation = validate_and_schedule(
                draft,
                revision_retrieved,
                conditions,
                route_provider=self.route_provider,
                policy=self.validation_policy,
                operational_provider=self.operational_provider,
                holiday_calendar=self.holiday_calendar,
            )
            retrieved = list(revision_retrieved)
            fallback_used = True

        if not validation.valid:
            validation_messages = [issue.message for issue in validation.issues]
            # Recombine all candidates already retrieved for each slot before
            # paying for or attempting any additional generation.
            fallback_draft = deterministic_draft(
                revision_retrieved,
                conditions,
            )
            fallback_validation = validate_and_schedule(
                fallback_draft,
                revision_retrieved,
                conditions,
                route_provider=self.route_provider,
                policy=self.validation_policy,
                operational_provider=self.operational_provider,
                holiday_calendar=self.holiday_calendar,
            )
            fallback_used = True
            if fallback_validation.valid:
                draft = fallback_draft
                validation = fallback_validation
                retrieved = list(revision_retrieved)

        if not validation.valid:
            # A deterministic correction that cannot satisfy the validator
            # means the current whitelist is insufficient. Re-run retrieval
            # with expanded geographic slots, then rebuild meals around the
            # newly selected tourism places. Do not send the same large
            # context to an LLM repair call.
            validation_messages = [issue.message for issue in validation.issues]
            retry_retrieved = self._retrieve_validation_retry_candidates(
                conditions=conditions,
                tourism_retrieved=tourism_retrieved,
                meal_slots=meal_slots,
                broad_fallback_slots=broad_fallback_slots,
                places_per_day_by_day=target_places_by_day,
                avoided_ids=avoided_ids,
            )
            candidate_retry_used = True
            candidate_retry_count = 1
            retry_draft = deterministic_draft(
                retry_retrieved,
                conditions,
            )
            retry_validation = validate_and_schedule(
                retry_draft,
                retry_retrieved,
                conditions,
                route_provider=self.route_provider,
                policy=self.validation_policy,
                operational_provider=self.operational_provider,
                holiday_calendar=self.holiday_calendar,
            )
            draft = retry_draft
            validation = retry_validation
            retrieved = list(retry_retrieved)
            revision_retrieved = list(retry_retrieved)
            fallback_used = True

        status = "completed" if validation.valid else "validation_failed"
        ready_for_booking = validation.valid and not validation.warnings
        recommendation_label = (
            "검증 완료 일정"
            if ready_for_booking
            else "AI 추천 일정 초안"
        )
        return {
            "status": status,
            "conditions": conditions.to_dict(),
            "optional_questions": list(condition_result.optional_questions),
            "message": (
                (
                    f"{recommendation_label}입니다. AIHub 유사 동선이 없어 "
                    "TourAPI 장소만으로 생성했습니다."
                    if route_strategy == "tourapi_only_fallback"
                    else f"{recommendation_label}입니다. AIHub 유사 동선 구조에 "
                    "TourAPI 장소를 배치했습니다."
                )
                if validation.valid
                else "TourAPI 후보 일정이 운영시간·거리 검증을 통과하지 못했습니다."
            ),
            "reference_trip": _selected_pattern_summary(route_context),
            "aihub_route_context": _safe_route_context(route_context),
            "slot_candidates": [item.to_dict() for item in retrieved],
            "revision_slot_candidates": [
                item.to_dict() for item in revision_retrieved
            ],
            "draft": draft.to_dict(),
            "itinerary": [stop.to_dict() for stop in validation.schedule],
            "validation": validation.to_dict(),
            "meta": {
                "input_mode": input_mode,
                "places_per_day": places_per_day,
                "tourism_places_per_day": places_per_day,
                "tourism_places_by_day": target_places_by_day,
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
                "candidate_retrieval_retry_used": candidate_retry_used,
                "candidate_retrieval_retry_count": candidate_retry_count,
                "validation_messages_before_fallback": validation_messages,
                "place_source": "tourapi_vector_candidates_only",
                "aihub_tourapi_mapping": "ignored",
                "aihub_original_slot_counts": original_slot_counts,
                "synthesized_route_days": synthesized_days,
                "synthesized_slot_count": synthesized_slot_count,
                "avoided_previous_content_ids": sorted(avoided_ids),
                "ready_for_booking": ready_for_booking,
                "recommendation_label": recommendation_label,
                "verification_warning_count": len(validation.warnings),
                "meal_search_strategy": (
                    "after_tourism_selection_radius_search"
                ),
                "route_metrics_provider": (
                    validation.schedule[0].route_source
                    if validation.schedule
                    else None
                ),
            },
        }

    def create_initial_itinerary(
        self,
        *,
        duration_days: int,
        party_size: int,
        local_transport: str,
        travel_style: str,
    ) -> dict[str, Any]:
        """Create the first itinerary from the four guided UI inputs."""

        condition_result = self.condition_service.from_guided_inputs(
            duration_days=duration_days,
            party_size=party_size,
            local_transport=local_transport,
            travel_style=travel_style,
        )
        result = self.run(
            selected_options=condition_result.conditions.to_dict(),
        )
        meta = dict(result.get("meta") or {})
        meta["interaction_flow"] = "guided_initial_itinerary_v1"
        meta["guided_input_fields"] = [
            "duration_days",
            "party_size",
            "local_transport",
            "travel_style",
        ]
        result["meta"] = meta
        return result

    def continue_itinerary(
        self,
        *,
        previous_result: Mapping[str, Any],
        message: str,
        history: Sequence[Mapping[str, str]] = (),
    ) -> dict[str, Any]:
        """Apply a natural-language request after the first itinerary exists."""

        if not message.strip():
            raise ValueError("message must not be blank")
        previous_conditions = previous_result.get("conditions")
        if not isinstance(previous_conditions, Mapping):
            return _revision_clarification(
                previous_result,
                "기존 여행 조건을 확인할 수 없어 요청을 반영할 수 없습니다.",
            )
        duration_days = int(previous_conditions.get("duration_days") or 0)
        slot_addition = _parse_tourism_slot_addition_request(
            message,
            duration_days=duration_days,
        )
        if slot_addition is not None:
            increments, clarification = slot_addition
            if clarification:
                return _revision_clarification(previous_result, clarification)
            current_counts = _current_tourism_places_by_day(
                previous_result,
                duration_days=duration_days,
            )
            target_counts = dict(current_counts)
            for day, increment in increments.items():
                target_counts[day] = target_counts.get(day, PLACES_PER_DAY) + increment
            if any(
                count > MAX_TOURISM_PLACES_PER_DAY
                for count in target_counts.values()
            ):
                return _revision_clarification(
                    previous_result,
                    "하루 관광지는 운영시간과 식사 시간을 고려해 최대 "
                    f"{MAX_TOURISM_PLACES_PER_DAY}곳까지 추가할 수 있습니다.",
                )
            result = self.run(
                selected_options=dict(previous_conditions),
                tourism_places_by_day=target_counts,
            )
            meta = dict(result.get("meta") or {})
            meta.update(
                {
                    "interaction_flow": "natural_language_revision_v1",
                    "edit_mode": "tourism_slot_addition",
                    "tourism_slot_increments": increments,
                    "previous_itinerary_preserved": False,
                }
            )
            result["meta"] = meta
            if result.get("status") == "completed":
                changed = ", ".join(
                    f"{day}일차 +{count}곳"
                    for day, count in sorted(increments.items())
                )
                result["message"] = (
                    f"요청하신 관광지 슬롯을 추가해 일정을 다시 구성했습니다: "
                    f"{changed}."
                )
            return result
        if (
            _is_full_regeneration_request(message)
            or _parse_replacement_request(message) is not None
        ):
            return self.revise(
                previous_result=previous_result,
                message=message,
            )
        result = self.run(
            message=message,
            history=history,
            current_conditions=previous_conditions,
            tourism_places_by_day=_current_tourism_places_by_day(
                previous_result,
                duration_days=duration_days,
            ),
        )
        meta = dict(result.get("meta") or {})
        meta.update(
            {
                "interaction_flow": "natural_language_revision_v1",
                "edit_mode": "condition_update_regeneration",
                "previous_itinerary_preserved": False,
            }
        )
        result["meta"] = meta
        if result.get("status") == "completed":
            result["message"] = (
                "기존 여행 조건에 추가 요청을 반영해 일정을 다시 구성했습니다."
            )
        return result

    def _retrieve_validation_retry_candidates(
        self,
        *,
        conditions: TravelConditions,
        tourism_retrieved: Sequence[SlotCandidates],
        meal_slots: Sequence[SlotRequest],
        broad_fallback_slots: Mapping[tuple[int, int], SlotRequest],
        places_per_day_by_day: Mapping[int, int],
        avoided_ids: set[int],
    ) -> list[SlotCandidates]:
        """Re-query TourAPI around the actual route and lock route-safe places."""

        max_radius = max_leg_distance_km(conditions)
        last_day = max(
            (item.slot.day for item in tourism_retrieved),
            default=conditions.duration_days or 1,
        )
        retry_tourism: list[SlotCandidates] = []
        selected_tourism: dict[tuple[int, int], RetrievedPlace] = {}
        used_ids = set(avoided_ids)
        by_day: dict[int, list[SlotCandidates]] = {}
        for item in tourism_retrieved:
            by_day.setdefault(item.slot.day, []).append(item)

        for day in sorted(by_day):
            day_items = sorted(
                by_day[day],
                key=lambda item: item.slot.sequence,
            )
            _, previous_coordinates = resolve_day_start_anchor(
                conditions,
                day=day,
            )
            if previous_coordinates is None and day_items:
                first_slot = day_items[0].slot
                if first_slot.latitude and first_slot.longitude:
                    previous_coordinates = (
                        first_slot.latitude,
                        first_slot.longitude,
                    )
            _, day_end_coordinates = resolve_day_end_anchor(
                conditions,
                day=day,
                last_day=last_day,
            )

            for index, item in enumerate(day_items):
                slot = item.slot
                current_radius = float(slot.radius_km or 0)
                expanded_radius = min(
                    max_radius,
                    max(current_radius * 1.5, min(max_radius, 12.0)),
                )
                retry_slot = replace(
                    slot,
                    latitude=(
                        previous_coordinates[0]
                        if previous_coordinates is not None
                        else slot.latitude
                    ),
                    longitude=(
                        previous_coordinates[1]
                        if previous_coordinates is not None
                        else slot.longitude
                    ),
                    radius_km=expanded_radius,
                    template_source="validation_retry_route_aware",
                )
                refreshed = self.slot_retriever.retrieve(
                    retry_slot,
                    conditions,
                )
                fallback_slot = broad_fallback_slots.get(
                    (slot.day, slot.sequence)
                )
                if not refreshed.candidates and fallback_slot is not None:
                    refreshed = self.slot_retriever.retrieve(
                        replace(
                            fallback_slot,
                            latitude=retry_slot.latitude,
                            longitude=retry_slot.longitude,
                            radius_km=expanded_radius,
                            template_source="validation_retry_broad",
                        ),
                        conditions,
                    )
                merged = _merge_slot_candidate_pools(refreshed, item)
                merged = _filter_avoided_candidates(
                    [merged],
                    avoided_ids,
                )[0]
                destination = (
                    day_end_coordinates
                    if index == len(day_items) - 1
                    else None
                )
                selected = self._select_route_safe_place(
                    merged,
                    conditions=conditions,
                    origin=previous_coordinates,
                    destination=destination,
                    max_distance_km=max_radius,
                    used_ids=used_ids,
                )
                if selected is not None:
                    used_ids.add(selected.content_id)
                    selected_tourism[
                        (slot.day, slot.sequence)
                    ] = selected
                    previous_coordinates = place_coordinates(selected)
                    merged = replace(merged, candidates=(selected,))
                retry_tourism.append(merged)

        tourism_draft = deterministic_draft(retry_tourism, conditions)
        selected_tourism = _selected_places_by_slot(
            tourism_draft,
            retry_tourism,
        )
        retry_meal_slots = [
            _anchor_meal_slot_to_selected_tourism(
                slot,
                selected_tourism,
                places_per_day=places_per_day_by_day[slot.day],
            )
            for slot in meal_slots
        ]
        retry_meals: list[SlotCandidates] = []
        for slot in retry_meal_slots:
            meal_result = self.slot_retriever.retrieve(slot, conditions)
            meal_result = _filter_avoided_candidates(
                [meal_result],
                avoided_ids,
            )[0]
            origin, destination = _meal_route_neighbors(
                slot,
                selected_tourism,
                conditions=conditions,
                places_per_day=places_per_day_by_day[slot.day],
                last_day=last_day,
            )
            selected_meal = self._select_route_safe_place(
                meal_result,
                conditions=conditions,
                origin=origin,
                destination=destination,
                max_distance_km=max_radius,
                used_ids=used_ids,
            )
            if selected_meal is not None:
                used_ids.add(selected_meal.content_id)
                meal_result = replace(
                    meal_result,
                    candidates=(selected_meal,),
                )
            retry_meals.append(meal_result)
        return sorted(
            [*retry_tourism, *retry_meals],
            key=lambda item: (item.slot.day, item.slot.sequence),
        )

    def _select_route_safe_place(
        self,
        item: SlotCandidates,
        *,
        conditions: TravelConditions,
        origin: tuple[float, float] | None,
        destination: tuple[float, float] | None,
        max_distance_km: float,
        used_ids: set[int],
    ) -> RetrievedPlace | None:
        """Choose the highest-scoring candidate whose adjacent legs are safe."""

        ranked: list[tuple[float, float, int, RetrievedPlace]] = []
        for candidate in item.candidates:
            if candidate.content_id in used_ids:
                continue
            coordinates = place_coordinates(candidate)
            if coordinates is None and (origin is not None or destination is not None):
                continue
            total_distance = 0.0
            route_safe = True
            for leg_origin, leg_destination in (
                (origin, coordinates),
                (coordinates, destination),
            ):
                if leg_origin is None or leg_destination is None:
                    continue
                try:
                    estimate = self.route_provider.estimate(
                        leg_origin,
                        leg_destination,
                        transport=conditions.local_transport or "mixed",
                    )
                except RouteProviderError:
                    route_safe = False
                    break
                if estimate.distance_km > max_distance_km:
                    route_safe = False
                    break
                total_distance += estimate.distance_km
            if route_safe:
                ranked.append(
                    (
                        -float(candidate.slot_score or 0.0),
                        total_distance,
                        candidate.content_id,
                        candidate,
                    )
                )
        if not ranked:
            return None
        ranked.sort(key=lambda value: value[:3])
        return ranked[0][3]

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

        if _is_full_regeneration_request(message):
            previous_conditions = previous_result.get("conditions")
            if not isinstance(previous_conditions, Mapping):
                return _revision_clarification(
                    previous_result,
                    "기존 여행 조건을 확인할 수 없어 다시 생성할 수 없습니다.",
                )
            previous_ids = [
                int(item["content_id"])
                for item in previous_result.get("itinerary", ())
                if isinstance(item, Mapping) and item.get("content_id") is not None
            ]
            regenerated = self.run(
                selected_options=dict(previous_conditions),
                avoid_content_ids=previous_ids,
                tourism_places_by_day=_current_tourism_places_by_day(
                    previous_result,
                    duration_days=int(
                        previous_conditions.get("duration_days") or 0
                    ),
                ),
            )
            meta = dict(regenerated.get("meta") or {})
            meta.update(
                {
                    "edit_mode": "full_regeneration",
                    "previous_place_count": len(previous_ids),
                }
            )
            regenerated["meta"] = meta
            if regenerated.get("status") == "completed":
                regenerated["message"] = (
                    "기존 여행 조건은 유지하고 이전 장소를 가능한 한 피해서 "
                    "일정을 처음부터 다시 생성했습니다."
                )
            return regenerated

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
            previous_result.get("revision_slot_candidates")
            or previous_result.get("slot_candidates")
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
                route_provider=self.route_provider,
                policy=self.validation_policy,
                operational_provider=self.operational_provider,
                holiday_calendar=self.holiday_calendar,
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
    tourism_places_by_day: Mapping[int, int],
    provisional_itinerary: Sequence[Mapping[str, Any]] = (),
    provisional_validation: Mapping[str, Any] | None = None,
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
    options = [
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
        },
        {
            "value": "enter_meal_region",
            "label": "식사 지역 지정",
            "description": (
                "식사할 읍·면·동 또는 관광지 주변 지역을 직접 입력합니다."
            ),
            "selected_options": {},
        },
        {
            "value": "change_meal_menu",
            "label": "원하는 메뉴 변경",
            "description": (
                "원하는 음식 메뉴를 바꿔 해당 반경에서 다시 검색합니다."
            ),
            "selected_options": {},
        },
    ]
    question = (
        f"{missing_text} 식당을 현재 검색 반경 "
        f"{current_radius:g}km 안에서 찾지 못했습니다. "
        "해당 식사 일정을 제외하거나, 식사 지역을 지정하거나, "
        "원하는 메뉴를 변경해 주세요."
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
        "itinerary": [dict(item) for item in provisional_itinerary],
        "validation": dict(provisional_validation or {}),
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
            "tourism_places_per_day": PLACES_PER_DAY,
            "tourism_places_by_day": dict(tourism_places_by_day),
            "meal_search_radius_km": current_radius,
            "provisional_tourism_schedule": bool(provisional_itinerary),
            "tourism_itinerary_preserved": True,
            "partial_result": True,
        },
    }


def _parse_tourism_slot_addition_request(
    message: str,
    *,
    duration_days: int,
) -> tuple[dict[int, int], str | None] | None:
    """Parse an explicit request to add tourism stops to selected days."""

    normalized = re.sub(r"\s+", " ", message.strip())
    compact = normalized.replace(" ", "")
    addition_terms = ("추가", "더넣", "늘려", "늘리")
    slot_terms = ("관광지", "장소", "일정", "슬롯", "코스")
    if not any(term in compact for term in addition_terms):
        return None
    if not any(term in compact for term in slot_terms):
        return None

    count_match = re.search(r"(\d+)\s*(?:곳|개|군데)", normalized)
    if count_match is not None:
        increment = int(count_match.group(1))
    elif re.search(r"(?:한\s*곳|한\s*군데|하나)", normalized):
        increment = 1
    elif re.search(r"(?:두\s*곳|두\s*군데|둘)", normalized):
        increment = 2
    elif re.search(r"(?:세\s*곳|세\s*군데|셋)", normalized):
        increment = 3
    else:
        increment = 1
    if increment <= 0:
        return {}, "추가할 관광지 수는 1곳 이상이어야 합니다."

    requested_days = {
        int(value)
        for value in re.findall(r"(\d+)\s*일차", normalized)
    }
    if not requested_days and any(
        token in compact for token in ("매일", "각일차", "하루마다")
    ):
        requested_days = set(range(1, duration_days + 1))
    if not requested_days:
        return (
            {},
            "관광지 슬롯을 추가할 일차를 알려주세요. "
            "예: '2일차에 관광지 1곳 추가해 주세요.'",
        )
    invalid_days = sorted(
        day for day in requested_days if not 1 <= day <= duration_days
    )
    if invalid_days:
        return (
            {},
            f"현재 여행 기간에 없는 일차입니다: {invalid_days}. "
            f"1~{duration_days}일차 중에서 선택해 주세요.",
        )
    return ({day: increment for day in sorted(requested_days)}, None)


def _current_tourism_places_by_day(
    result: Mapping[str, Any],
    *,
    duration_days: int,
) -> dict[int, int]:
    """Restore per-day tourism counts from metadata or the visible itinerary."""

    counts = {
        day: PLACES_PER_DAY
        for day in range(1, max(duration_days, 0) + 1)
    }
    meta = result.get("meta")
    raw_counts = (
        meta.get("tourism_places_by_day")
        if isinstance(meta, Mapping)
        else None
    )
    if isinstance(raw_counts, Mapping):
        for day in counts:
            value = raw_counts.get(day, raw_counts.get(str(day)))
            if value is not None:
                counts[day] = max(1, int(value))
        return counts

    itinerary = result.get("itinerary")
    if isinstance(itinerary, list):
        observed = {day: 0 for day in counts}
        for item in itinerary:
            if not isinstance(item, Mapping):
                continue
            day = int(item.get("day") or 0)
            if day not in observed:
                continue
            if (
                item.get("slot_kind") == "meal"
                or item.get("meal_type") in {"breakfast", "lunch", "dinner"}
            ):
                continue
            observed[day] += 1
        for day, value in observed.items():
            if value:
                counts[day] = value
    return counts


def _resolve_tourism_places_by_day(
    *,
    duration_days: int,
    overrides: Mapping[int, int] | None,
) -> dict[int, int]:
    if duration_days <= 0:
        raise ValueError("duration_days must be positive")
    result = {
        day: PLACES_PER_DAY
        for day in range(1, duration_days + 1)
    }
    raw = overrides or {}
    for day in result:
        value = raw.get(day, raw.get(str(day)))  # type: ignore[arg-type]
        if value is None:
            continue
        count = int(value)
        if not 1 <= count <= MAX_TOURISM_PLACES_PER_DAY:
            raise ValueError(
                "tourism places per day must be between 1 and "
                f"{MAX_TOURISM_PLACES_PER_DAY}"
            )
        result[day] = count
    return result


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


def _is_full_regeneration_request(message: str) -> bool:
    normalized = re.sub(r"\s+", "", message).lower()
    regeneration_terms = (
        "처음부터다시",
        "전체일정다시",
        "일정을다시짜",
        "새일정으로",
        "전부다시",
        "전체재생성",
    )
    return any(term in normalized for term in regeneration_terms)


def _selected_places_by_slot(
    draft: ItineraryDraft,
    retrieved: Sequence[SlotCandidates],
) -> dict[tuple[int, int], RetrievedPlace]:
    candidates = {
        (item.slot.day, item.slot.sequence, place.content_id): place
        for item in retrieved
        for place in item.candidates
    }
    return {
        (choice.day, choice.slot_sequence): place
        for choice in draft.choices
        if (
            place := candidates.get(
                (choice.day, choice.slot_sequence, choice.content_id)
            )
        )
        is not None
    }


def _filter_avoided_candidates(
    retrieved: Sequence[SlotCandidates],
    avoided_ids: set[int],
) -> list[SlotCandidates]:
    """Prefer a new candidate while preserving a slot that has no alternative."""

    if not avoided_ids:
        return list(retrieved)
    return [
        replace(
            item,
            candidates=(
                filtered
                if (
                    filtered := tuple(
                        place
                        for place in item.candidates
                        if place.content_id not in avoided_ids
                    )
                )
                else item.candidates
            ),
        )
        for item in retrieved
    ]


def _merge_slot_candidate_pools(
    primary: SlotCandidates,
    secondary: SlotCandidates,
) -> SlotCandidates:
    """Keep refreshed ranking first while retaining unique prior candidates."""

    merged: list[RetrievedPlace] = []
    seen: set[int] = set()
    for place in (*primary.candidates, *secondary.candidates):
        if place.content_id in seen:
            continue
        seen.add(place.content_id)
        merged.append(place)
    return replace(
        primary,
        candidates=tuple(merged),
    )


def _anchor_meal_slot_to_selected_tourism(
    slot: SlotRequest,
    selected: Mapping[tuple[int, int], RetrievedPlace],
    *,
    places_per_day: int,
) -> SlotRequest:
    if slot.meal_type == "breakfast":
        tourism_sequence = 1
    elif slot.meal_type == "lunch":
        tourism_sequence = max(1, round(places_per_day * 0.4))
    else:
        tourism_sequence = places_per_day
    anchor = selected.get((slot.day, tourism_sequence))
    if anchor is None:
        return slot
    return replace(
        slot,
        latitude=anchor.latitude or slot.latitude,
        longitude=anchor.longitude or slot.longitude,
        route_anchor=anchor.title,
        template_source="meal_after_tourism_selection",
    )


def _meal_route_neighbors(
    slot: SlotRequest,
    selected: Mapping[tuple[int, int], RetrievedPlace],
    *,
    conditions: TravelConditions,
    places_per_day: int,
    last_day: int,
) -> tuple[
    tuple[float, float] | None,
    tuple[float, float] | None,
]:
    """Return the route legs immediately before and after a meal slot."""

    if slot.meal_type == "breakfast":
        _, origin = resolve_day_start_anchor(conditions, day=slot.day)
        destination_place = selected.get((slot.day, 1))
        return origin, (
            place_coordinates(destination_place)
            if destination_place is not None
            else None
        )
    if slot.meal_type == "lunch":
        previous_sequence = max(1, round(places_per_day * 0.4))
        next_sequence = min(places_per_day, previous_sequence + 1)
        previous_place = selected.get((slot.day, previous_sequence))
        next_place = selected.get((slot.day, next_sequence))
        return (
            place_coordinates(previous_place)
            if previous_place is not None
            else None
        ), (
            place_coordinates(next_place)
            if next_place is not None
            else None
        )

    previous_place = selected.get((slot.day, places_per_day))
    _, destination = resolve_day_end_anchor(
        conditions,
        day=slot.day,
        last_day=last_day,
    )
    return (
        place_coordinates(previous_place)
        if previous_place is not None
        else None
    ), destination


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
        "message": question,
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
    tourism_places_by_day: Mapping[int, int] | None = None,
) -> dict[str, Any]:
    pattern = _selected_pattern(route_context)
    route_strategy = (
        "aihub_pattern"
        if pattern
        else "tourapi_only_fallback"
    )
    slots_payload: list[dict[str, Any]] = []
    candidate_limit = _positive_env_int(
        "RAG_PROMPT_CANDIDATES_PER_SLOT",
        3,
    )
    for item in slot_candidates:
        candidates = [
            {
                "content_id": place.content_id,
                "title": place.title,
                "itinerary_role": place.itinerary_role,
                "opening_hours": place.opening_hours[:240],
                "closed_days": place.closed_days[:160],
                "parking": place.parking[:160],
                "rating": place.rating,
                "distance_km": place.distance_km,
                "operating_information_known": bool(
                    place.opening_hours or place.closed_days
                ),
            }
            for place in item.candidates[:candidate_limit]
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
        "explicit_frontend_fields": sorted(
            str(key) for key in (frontend_selections or {})
        ),
        "user_conditions": _compact_conditions_for_itinerary_prompt(
            conditions
        ),
        "slots": slots_payload,
        "policy": {
            "route_strategy": route_strategy,
            "tourism_places_per_day": PACE_SLOTS_PER_DAY.get(
                conditions.pace or "",
                PLACES_PER_DAY,
            ),
            "tourism_places_by_day": dict(
                tourism_places_by_day
                or _resolve_tourism_places_by_day(
                    duration_days=int(conditions.duration_days or 0),
                    overrides=None,
                )
            ),
            "meal_slots_per_day": (
                3 if conditions.include_breakfast is True else 2
            ),
            "every_slot_required": True,
            "duplicate_content_ids_allowed": False,
            "max_leg_distance_km": max_leg_distance_km(conditions),
        },
    }


def _positive_env_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _compact_conditions_for_itinerary_prompt(
    conditions: TravelConditions,
) -> dict[str, Any]:
    """Send only constraints that can affect ID and stay-time selection."""

    payload = conditions.to_dict()
    allowed_fields = (
        "duration_days",
        "party_type",
        "local_transport",
        "preferred_visit_types",
        "pace",
        "arrival_time",
        "departure_time",
        "entry_point",
        "exit_point",
        "accommodation_address",
        "preferred_places",
        "preferred_foods",
        "preferred_meal_regions",
        "include_breakfast",
        "skipped_meals",
        "travel_styles",
        "must_visit_places",
        "must_visit_content_ids",
        "required_day_itineraries",
        "excluded_places",
        "excluded_foods",
        "avoid_long_distance",
        "opening_hours_constraints",
        "parking_required",
        "indoor_preference",
        "mobility_constraints",
    )
    return {
        key: payload[key]
        for key in allowed_fields
        if payload.get(key) not in (None, "", [], {})
    }


def create_rag_orchestrator(
    *,
    project_root: str | Path | None = None,
    env_file: str | Path | None = None,
    route_provider: RouteMetricsProvider | None = None,
    validation_policy: ValidationPolicy | None = None,
    operational_provider: PlaceOperationalFactsProvider | None = None,
    holiday_calendar: HolidayCalendar | None = None,
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
    configured_operational, configured_holiday_calendar = (
        create_operational_services_from_env(project_root=root)
    )
    return RagOrchestrator(
        condition_service=condition_service,
        route_adapter=route_adapter,
        slot_retriever=SlotRetriever(
            place_service,
            operational_provider=(
                operational_provider or configured_operational
            ),
        ),
        llm=llm,
        route_provider=(
            route_provider or create_route_metrics_provider_from_env()
        ),
        validation_policy=validation_policy,
        operational_provider=(
            operational_provider or configured_operational
        ),
        holiday_calendar=(
            holiday_calendar or configured_holiday_calendar
        ),
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
