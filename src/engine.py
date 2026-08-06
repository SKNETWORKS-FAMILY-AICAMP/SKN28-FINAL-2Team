from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Sequence

from .aihub.similarity import (
    SLOT_ITINERARY_ROLES,
    SLOT_TARGET_COLLECTIONS,
    AIHubPatternService,
)
from .common.env import load_env_file
from .llm import LLMService, create_llm_service
from .models import ItinerarySlot, ItineraryState, SlotAddRequest, SlotCandidate, TravelCondition, apply_delta, infer_affected_slots

from .planner import PlannerConfig, select_candidates
from .rag import PlaceSearchFilters, PlaceSearchService, create_place_search_service
from .rag.models import RetrievedPlace
from .recommender import create_pattern_service

DEFAULT_SEARCH_TOP_K = 8
_DEFAULT_DAY_ROLES: tuple[str, ...] = ("visit", "food", "visit", "food")

_DEFAULT_STAY_MINUTES_BY_ROLE: dict[str, int] = {
    "visit": 90,
    "activity": 120,
    "food": 60,
    "shopping": 30,
}

_TARGET_COLLECTION_TO_ROLE: dict[str, str] = {
    "restaurants": "food",
    "shopping": "shopping",
    "activities": "activity",
    "attractions": "visit",
}
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class AppContainer:
    retrieval_service: PlaceSearchService
    pattern_service: AIHubPatternService
    llm_service: LLMService
    planner_config: PlannerConfig


def create_container(
    project_root: str | Path,
    *,
    planner_config: PlannerConfig | None = None,
) -> AppContainer:
    project_root = Path(project_root)
    load_env_file(project_root / ".env")

    retrieval_service = create_place_search_service(project_root=project_root)
    pattern_service = create_pattern_service(project_root=project_root)
    llm_service = create_llm_service()

    return AppContainer(
        retrieval_service=retrieval_service,
        pattern_service=pattern_service,
        llm_service=llm_service,
        planner_config=planner_config or PlannerConfig(),
    )


class ItineraryEngine:

    def __init__(self, container: AppContainer) -> None:
        self._container = container

    # ------------------------------------------------------------------
    # Initial itinerary creation
    # ------------------------------------------------------------------
    def create_itinerary(self, user_text: str) -> ItineraryState:
        container = self._container

        condition = container.llm_service.extract_travel_condition(user_text)
        day_templates = self._build_day_structure(condition)

        slots: list[ItinerarySlot] = []
        used_content_ids: set[int] = set()

        for day in day_templates:
            for slot_template in day["slots"]:
                slot = self._search_and_plan_slot(
                    condition,
                    day_no=day["day"],
                    slot_template=slot_template,
                    exclude_content_ids=used_content_ids,
                )
                used_content_ids.update(
                    candidate.content_id for candidate in slot.candidates
                )
                slots.append(slot)

        self._force_include_must_visit_places(
            condition,
            slots,
            used_content_ids,
        )

        days_with_candidates = _group_slots_by_day(slots)

        itinerary = container.llm_service.generate_itinerary(
            condition,
            days_with_candidates,
        )

        print("=" * 50)
        print("LLM 결과 day 수:", len(itinerary["days"]))
        print(itinerary)

        return ItineraryState(
            condition=condition,
            slots=slots,
            itinerary=itinerary,
            used_content_ids=used_content_ids,
        )
    # ------------------------------------------------------------------
    # Free-chat modification
    # ------------------------------------------------------------------
    def update_itinerary_from_chat(
        self, state: ItineraryState, user_text: str
    ) -> ItineraryState:
        container = self._container
        delta = container.llm_service.extract_condition_delta(state.condition, user_text)
        new_condition = apply_delta(state.condition, delta)

        if delta.is_empty():
            print("[revise] delta.is_empty() == True -> 변경할 내용 없음, 그대로 반환")
            return ItineraryState(
                condition=new_condition,
                slots=state.slots,
                itinerary=state.itinerary,
                used_content_ids=set(state.used_content_ids),
            )

        affected_roles = set(infer_affected_slots(delta))
        print("[revise] affected_roles :", affected_roles)
        used_content_ids = set(state.used_content_ids)
        updated_slots: list[ItinerarySlot] = []
        re_searched_keys: set[tuple[int, int]] = set()

        for slot in state.slots:
            if slot.role not in affected_roles:
                updated_slots.append(slot)
                continue

            own_previous_ids = {candidate.content_id for candidate in slot.candidates}
            exclude_ids = used_content_ids - own_previous_ids
            refreshed = self._search_and_plan_slot(
                new_condition,
                day_no=slot.day,
                slot_template={
                    "sequence": slot.sequence,
                    "role": slot.role,
                    "target_collections": list(slot.target_collections),
                    "itinerary_roles": list(slot.itinerary_roles),
                    "stay_minutes": slot.stay_minutes,
                    "location_hint": slot.location_hint,
                },
                exclude_content_ids=exclude_ids,
                extra_request=delta.notes or None,
            )
            used_content_ids -= own_previous_ids
            used_content_ids.update(candidate.content_id for candidate in refreshed.candidates)
            updated_slots.append(refreshed)
            re_searched_keys.add((refreshed.day, refreshed.sequence))

        forced_slots = self._force_include_must_visit_places(
            new_condition, updated_slots, used_content_ids
        )

        new_slots = self._create_added_slots(
            new_condition,
            delta.add_slots,
            updated_slots,
            used_content_ids,
            extra_request=delta.notes or None,
        )
        updated_slots.extend(new_slots)

        print("[revise] re_searched_keys:", re_searched_keys)
        print(
            "[revise] forced_slots (must-visit):",
            [(s.day, s.sequence, s.role) for s in forced_slots],
        )
        print(
            "[revise] new_slots (add_slots)    :",
            [(s.day, s.sequence, s.role, len(s.candidates)) for s in new_slots],
        )

        changed_keys = (
            re_searched_keys
            | {(slot.day, slot.sequence) for slot in forced_slots}
            | {(slot.day, slot.sequence) for slot in new_slots}
        )
        changed_slot_payloads = [
            slot.to_dict() for slot in updated_slots if (slot.day, slot.sequence) in changed_keys
        ]
        print("[revise] changed_keys       :", changed_keys)
        print("[revise] changed_slot_payloads count:", len(changed_slot_payloads))

        if changed_slot_payloads:
            itinerary = container.llm_service.revise_itinerary(
                new_condition, state.itinerary, changed_slot_payloads
            )
        else:
            print("[revise] changed_slot_payloads가 비어있어서 LLM 재구성 없이 그대로 반환")
            itinerary = state.itinerary

        return ItineraryState(
            condition=new_condition,
            slots=updated_slots,
            itinerary=itinerary,
            used_content_ids=used_content_ids,
        )

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    def _search_and_plan_slot(
        self,
        condition: TravelCondition,
        *,
        day_no: int,
        slot_template: dict[str, Any],
        exclude_content_ids: set[int],
        extra_request: str | None = None,
    ) -> ItinerarySlot:
        container = self._container
        role = slot_template["role"]

        query = container.llm_service.generate_search_query(
            condition, slot_role=role, day=day_no, extra_request=extra_request
        )
        filters = PlaceSearchFilters(
            target_collections=tuple(slot_template["target_collections"]),
            itinerary_roles=tuple(slot_template["itinerary_roles"]),
            route_eligible=True,
            schedule_eligible=True,
        )
        response = container.retrieval_service.search_places(
            query, filters=filters, top_k=DEFAULT_SEARCH_TOP_K
        )
        candidates = select_candidates(
            response.places,
            condition,
            role=role,
            location_hint=slot_template.get("location_hint"),
            exclude_content_ids=exclude_content_ids,
            config=container.planner_config,
        )
        return ItinerarySlot(
            day=day_no,
            sequence=slot_template["sequence"],
            role=role,
            target_collections=tuple(slot_template["target_collections"]),
            itinerary_roles=tuple(slot_template["itinerary_roles"]),
            stay_minutes=slot_template.get("stay_minutes"),
            location_hint=slot_template.get("location_hint"),
            query=query,
            candidates=candidates,
        )

    def _force_include_must_visit_places(
        self,
        condition: TravelCondition,
        slots: list[ItinerarySlot],
        used_content_ids: set[int],
    ) -> list[ItinerarySlot]:

        if not condition.must_visit_places:
            return []

        already_covered = {
            _normalize_title(candidate.title)
            for slot in slots
            for candidate in slot.candidates
        }
        slots_by_role: dict[str, list[ItinerarySlot]] = {}
        for slot in slots:
            slots_by_role.setdefault(slot.role, []).append(slot)

        touched_slots: list[ItinerarySlot] = []
        for place_name in condition.must_visit_places:
            normalized_name = _normalize_title(place_name)
            if not normalized_name or normalized_name in already_covered:
                continue

            response = self._container.retrieval_service.search_places(
                place_name, filters=PlaceSearchFilters(), top_k=3
            )
            if not response.places:
                continue
            match = _best_name_match(response.places, place_name)

            role = _infer_role_from_tags(match.tags)
            role_slots = slots_by_role.get(role) or slots_by_role.get("visit") or slots
            if not role_slots:
                continue
            target_slot = min(
                role_slots,
                key=lambda slot: (
                    any(candidate.forced for candidate in slot.candidates),
                    len(slot.candidates),
                ),
            )

            target_slot.candidates.insert(
                0,
                SlotCandidate(
                    content_id=match.content_id,
                    title=match.title,
                    final_score=1.0,
                    similarity_score=match.similarity_score,
                    place=match.to_dict(),
                    forced=True,
                ),
            )
            used_content_ids.add(match.content_id)
            already_covered.add(_normalize_title(match.title))
            if target_slot not in touched_slots:
                touched_slots.append(target_slot)

        return touched_slots

    def _create_added_slots(
        self,
        condition: TravelCondition,
        add_slot_requests: tuple[SlotAddRequest, ...],
        existing_slots: list[ItinerarySlot],
        used_content_ids: set[int],
        *,
        extra_request: str | None = None,
    ) -> list[ItinerarySlot]:

        if not add_slot_requests:
            return []

        available_days = sorted({slot.day for slot in existing_slots})
        if not available_days:
            return []

        new_slots: list[ItinerarySlot] = []

        for request in add_slot_requests:
            target_day = (
                request.day if request.day in available_days else available_days[0]
            )

            day_slots = [
                slot for slot in (*existing_slots, *new_slots) if slot.day == target_day
            ]
            next_sequence = max((slot.sequence for slot in day_slots), default=0) + 1

            # 같은 day에 참고할 슬롯이 있으면 위치 힌트를 재사용해서, 새로 검색되는
            # 장소가 그날 동선(지역)에서 크게 벗어나지 않도록 한다.
            reference = next(
                (slot for slot in day_slots if slot.role == request.role),
                day_slots[0] if day_slots else None,
            )
            location_hint = reference.location_hint if reference else None
            stay_minutes = (
                reference.stay_minutes
                if reference is not None and reference.role == request.role
                else _DEFAULT_STAY_MINUTES_BY_ROLE.get(request.role, 60)
            )

            for _ in range(request.count):
                slot_template = {
                    "sequence": next_sequence,
                    "role": request.role,
                    "target_collections": list(
                        SLOT_TARGET_COLLECTIONS.get(request.role, ())
                    ),
                    "itinerary_roles": list(
                        SLOT_ITINERARY_ROLES.get(request.role, ())
                    ),
                    "stay_minutes": stay_minutes,
                    "location_hint": location_hint,
                }

                created = self._search_and_plan_slot(
                    condition,
                    day_no=target_day,
                    slot_template=slot_template,
                    exclude_content_ids=used_content_ids,
                    extra_request=extra_request,
                )

                if not created.candidates:
                    # 검색 결과가 없으면 빈 슬롯을 추가하지 않고 건너뛴다.
                    print(
                        f"[revise] _create_added_slots: day={target_day} "
                        f"role={request.role} sequence={next_sequence} "
                        "-> 후보 0개, 건너뜀"
                    )
                    continue

                used_content_ids.update(
                    candidate.content_id for candidate in created.candidates
                )
                new_slots.append(created)
                next_sequence += 1

        return new_slots


    def _build_day_structure(self, condition: TravelCondition) -> list[dict[str, Any]]:
        print("=" * 50)
        print("사용자 요청 일수:", condition.duration_days)

        matches = self._container.pattern_service.find_reference_trips(condition)

        if matches:
            context = self._container.pattern_service.build_llm_context(condition)
            reference_patterns = context.get("reference_trip_patterns") or []

            if reference_patterns:
                days = reference_patterns[0].get("days") or []

                print("AIHub 패턴 일수:", len(days))
                print(days)

                if days:
                    while len(days) < condition.duration_days:
                        new_day = {
                            **days[-1],
                            "day": len(days) + 1,
                        }
                        days.append(new_day)

                    days = days[:condition.duration_days]

                    print("보정 후 Day 수:", len(days))

                    return days

        print("기본 구조 사용")
        return _default_day_structure(condition)

def _normalize_title(title: str) -> str:
    return _WHITESPACE_RE.sub("", title).strip().lower()


def _infer_role_from_tags(tags: Sequence[str]) -> str:
    for tag in tags:
        if not tag.startswith("target_collection:"):
            continue
        role = _TARGET_COLLECTION_TO_ROLE.get(tag.split(":", 1)[1])
        if role:
            return role
    return "visit"


def _best_name_match(places: Sequence[RetrievedPlace], name: str) -> RetrievedPlace:
    normalized_name = _normalize_title(name)
    for place in places:
        normalized_title = _normalize_title(place.title)
        if normalized_name in normalized_title or normalized_title in normalized_name:
            return place
    return places[0]


def _group_slots_by_day(slots: list[ItinerarySlot]) -> list[dict[str, Any]]:
    days: dict[int, list[dict[str, Any]]] = {}
    for slot in slots:
        days.setdefault(slot.day, []).append(slot.to_dict())
    return [
        {"day": day_no, "slots": sorted(day_slots, key=lambda item: item["sequence"])}
        for day_no, day_slots in sorted(days.items())
    ]


def _default_day_structure(condition: TravelCondition) -> list[dict[str, Any]]:
    days: list[dict[str, Any]] = []
    for day_no in range(1, condition.duration_days + 1):
        slots = [
            {
                "sequence": sequence,
                "role": role,
                "target_collections": list(SLOT_TARGET_COLLECTIONS[role]),
                "itinerary_roles": list(SLOT_ITINERARY_ROLES[role]),
                "stay_minutes": 90,
                "location_hint": None,
            }
            for sequence, role in enumerate(_DEFAULT_DAY_ROLES, start=1)
        ]
        days.append({"day": day_no, "region": None, "slot_count": len(slots), "slots": slots})
    return days
