from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Sequence

from .aihub.similarity import AIHubPatternService

from .mappings.trip_feature_mapping import (
    SLOT_ITINERARY_ROLES,
    SLOT_TARGET_COLLECTIONS,
    get_visit_area_type_mapping,
)

from .mappings.trip_feature_mapping import (
    SLOT_ITINERARY_ROLES,
    SLOT_TARGET_COLLECTIONS,
)
from .common.env import load_env_file
from .llm import LLMService, create_llm_service
from .models import (
    ItinerarySlot,
    ItineraryState,
    SlotAddRequest,
    SlotCandidate,
    TravelCondition,
    apply_delta,
    infer_affected_slots,
)
from .planner import PlannerConfig, select_candidates
from .rag import PlaceSearchFilters, PlaceSearchService, create_place_search_service
from .rag.models import RetrievedPlace
from .recommender import create_pattern_service

DEFAULT_SEARCH_TOP_K = 15

# --- AIHub(이동 패턴) + RAG(관광지 후보) 조합 (초기 일정 생성) ---
# 각 모듈은 서로 다른 질문에 답한다:
#   AIHub -> "비슷한 사람들은 어떻게 이동했는가?" (이름 없는 순서/흐름 패턴)
#   RAG   -> "사용자가 원하는 스타일/자유 요청에 맞는 장소는 어디인가?"
#            (실제로 슬롯에 채워 넣을 수 있는 유일한 후보군)
# Planner가 결정한 슬롯 구조(_default_day_structure)는 그대로 유지하고,
# RAG 후보만으로 슬롯을 채운 뒤, AIHub 이동 패턴은 LLM이 순서를 정할 때
# 참고자료로만 사용한다.
RAG_CANDIDATE_POOL_TOP_K = 40

_DEFAULT_DAY_ROLES: tuple[str, ...] = ("visit", "activity", "food", "visit", "food")
_DEFAULT_STAY_MINUTES_BY_ROLE: dict[str, int] = {
    "visit": 90,
    "activity": 90,
    "food": 60,
    "shopping": 60,
}
# Reverse of aihub.similarity.SLOT_TARGET_COLLECTIONS, used to guess which
# itinerary slot role a specific must-visit place belongs to. "attractions"
# is shared by visit/activity, so it defaults to "visit" -- good enough for
# picking *a* slot to force the place into.
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
    """The single pipeline entry point the frontend/API layer talks to."""

    def __init__(self, container: AppContainer) -> None:
        self._container = container

    # ------------------------------------------------------------------
    # Initial itinerary creation
    # ------------------------------------------------------------------
    def create_itinerary(self, user_text: str) -> ItineraryState:
        container = self._container

        condition = container.llm_service.extract_travel_condition(user_text)

        # ------------------------------------------------------------
        # 1) 슬롯 구조는 Planner가 결정한다 (AIHub의 하루 방문 개수는
        #    참고하지 않는다). 슬롯 개수/역할은 이후 절대 줄이거나
        #    늘리지 않는다.
        # ------------------------------------------------------------
        day_templates = _default_day_structure(condition)

        # ------------------------------------------------------------
        # 2) RAG: 실제로 슬롯에 채워 넣을 수 있는 유일한 관광지 후보군.
        #    role에 국한하지 않고 폭넓게 검색한 뒤, role별로 나눠 둔다.
        # ------------------------------------------------------------
        rag_pool = self._collect_rag_candidates(condition)
        pool_by_role = _bucket_by_role(rag_pool)

        # ------------------------------------------------------------
        # 3) AIHub: 실제 장소 이름이 아니라, 여러 유사 여행에서 공통적으로
        #    나타나는 "이동 패턴"(방문 순서·흐름)만 요약해서 LLM 참고자료로
        #    전달한다. 특정 여행 하나를 그대로 따르지 않도록 top-K 여행을
        #    종합한다.
        # ------------------------------------------------------------
        movement_patterns = self._build_movement_pattern_context(condition)

        print("=" * 50)
        print(f"[candidate-pool] RAG 후보 {len(rag_pool)}개")
        print(
            "[candidate-pool] role별 개수:",
            {role: len(places) for role, places in pool_by_role.items()},
        )
        print("[movement-pattern] AIHub 참고 패턴:", movement_patterns)

        # ------------------------------------------------------------
        # 4) RAG 후보 풀에서 슬롯(role)에 맞는 후보만 선별한다.
        #    풀에 해당 role 후보가 없을 때만 즉석 검색으로 보강한다.
        # ------------------------------------------------------------
        slots: list[ItinerarySlot] = []
        used_content_ids: set[int] = set()

        for day in day_templates:
            for slot_template in day["slots"]:
                slot = self._plan_slot_from_pool(
                    condition,
                    day_no=day["day"],
                    slot_template=slot_template,
                    pool_by_role=pool_by_role,
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

        # ------------------------------------------------------------
        # 5) LLM은 장소를 검색하지 않는다. Planner의 슬롯 구조를 유지하고,
        #    RAG 후보 안에서만 선택하며, AIHub 이동 패턴은 순서를 정할 때
        #    참고자료로만 사용해 최종 일정을 완성한다.
        # ------------------------------------------------------------
        itinerary = container.llm_service.generate_itinerary(
            condition,
            days_with_candidates,
            movement_patterns=movement_patterns,
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
        self,
        state: ItineraryState,
        user_text: str,
    ) -> ItineraryState:
        container = self._container

        delta = container.llm_service.extract_condition_delta(
            state.condition,
            user_text,
        )

        new_condition = apply_delta(
            state.condition,
            delta,
        )

        if delta.is_empty():
            return ItineraryState(
                condition=new_condition,
                slots=state.slots,
                itinerary=state.itinerary,
                used_content_ids=set(state.used_content_ids),
            )

        affected_roles = set(
            infer_affected_slots(delta)
        )

        used_content_ids = set(
            state.used_content_ids
        )

        updated_slots: list[ItinerarySlot] = []
        re_searched_keys: set[tuple[int, int]] = set()

        for slot in state.slots:
            if slot.role not in affected_roles:
                updated_slots.append(slot)
                continue

            own_previous_ids = {
                candidate.content_id
                for candidate in slot.candidates
            }

            exclude_ids = (
                used_content_ids - own_previous_ids
            )

            refreshed = self._search_and_plan_slot(
                new_condition,
                day_no=slot.day,
                slot_template={
                    "sequence": slot.sequence,
                    "role": slot.role,
                    "target_collections": list(
                        slot.target_collections
                    ),
                    "itinerary_roles": list(
                        slot.itinerary_roles
                    ),
                    "stay_minutes": slot.stay_minutes,
                    "location_hint": slot.location_hint,
                },
                exclude_content_ids=exclude_ids,
                extra_request=delta.notes or None,
            )

            used_content_ids -= own_previous_ids

            used_content_ids.update(
                candidate.content_id
                for candidate in refreshed.candidates
            )

            updated_slots.append(refreshed)

            re_searched_keys.add(
                (
                    refreshed.day,
                    refreshed.sequence,
                )
            )

        # "카페 하나 더 추가해줘"처럼
        # 기존 슬롯 교체가 아니라 새 슬롯 추가 요청 처리
        added_slots = self._create_added_slots(
            new_condition,
            delta.add_slots,
            updated_slots,
            used_content_ids,
            extra_request=delta.notes or None,
        )

        updated_slots.extend(added_slots)

        forced_slots = self._force_include_must_visit_places(
            new_condition,
            updated_slots,
            used_content_ids,
        )

        changed_keys = (
            re_searched_keys
            | {
                (slot.day, slot.sequence)
                for slot in forced_slots
            }
            | {
                (slot.day, slot.sequence)
                for slot in added_slots
            }
        )

        changed_slot_payloads = [
            slot.to_dict()
            for slot in updated_slots
            if (
                slot.day,
                slot.sequence,
            ) in changed_keys
        ]

        if changed_slot_payloads:
            itinerary = container.llm_service.revise_itinerary(
                new_condition,
                state.itinerary,
                changed_slot_payloads,
            )
        else:
            itinerary = state.itinerary

        return ItineraryState(
            condition=new_condition,
            slots=updated_slots,
            itinerary=itinerary,
            used_content_ids=used_content_ids,
        )

    # ------------------------------------------------------------------
    # AIHub 이동 패턴 / RAG 후보군 조회
    # ------------------------------------------------------------------
    def _build_movement_pattern_context(
        self,
        condition: TravelCondition,
    ) -> dict[str, Any]:
        """AIHub 브랜치: "비슷한 사람들은 어떻게 이동했는가?"

        실제 관광지 이름, 숙소 위치, 하루 방문 개수, 일정 전체 구성은
        절대 포함하지 않는다. 특정 여행 하나를 그대로 따르지 않도록,
        동행/기간이 유사한 top-K 여행에서 공통적으로 나타나는
        "역할(role) 순서"와 "흐름(role -> role 전이)"만 집계해서
        LLM 참고자료로 돌려준다.
        """

        container = self._container
        matches = container.pattern_service.find_reference_trips(condition)
        if not matches:
            return {"available": False}

        travel_ids = [match.profile.travel_id for match in matches]
        routes = container.pattern_service.repository.fetch_trip_routes(travel_ids)

        rows_by_trip: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in routes:
            rows_by_trip[str(row["travel_id"])].append(row)

        role_sequences: list[tuple[str, ...]] = []
        transition_counts: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

        for rows in rows_by_trip.values():
            rows_by_day: dict[int, list[dict[str, Any]]] = defaultdict(list)
            for row in rows:
                type_code = str(row.get("visit_area_type_cd") or "")
                if type_code in {"9", "21", "22", "23", "24"}:
                    # 숙소/이동/비관광 데이터는 이동 패턴 분석 대상에서 제외한다.
                    continue
                day_no = max(int(row.get("day_no") or 1), 1)
                rows_by_day[day_no].append(row)

            for day_rows in rows_by_day.values():
                ordered = sorted(
                    day_rows,
                    key=lambda item: int(item.get("visit_order") or 0),
                )
                roles_list = []

                for row in ordered:
                    mapping = get_visit_area_type_mapping(
                        str(row.get("visit_area_type_cd") or "")
                    )

                    if mapping and mapping.slot_role in SLOT_TARGET_COLLECTIONS:
                        roles_list.append(mapping.slot_role)

                roles = tuple(roles_list)
                if not roles:
                    continue
                role_sequences.append(roles)
                for previous, current in zip(roles, roles[1:]):
                    transition_counts[previous][current] += 1

        if not role_sequences:
            return {"available": False}

        sequence_counts = Counter(role_sequences)
        most_common_sequence, support = sequence_counts.most_common(1)[0]

        role_transitions = []
        for previous, next_counts in transition_counts.items():
            total = sum(next_counts.values())
            if not total:
                continue
            best_next, best_count = max(next_counts.items(), key=lambda item: item[1])
            role_transitions.append(
                {
                    "after": previous,
                    "commonly_followed_by": best_next,
                    "share": round(best_count / total, 2),
                }
            )

        return {
            "available": True,
            "reference_trip_count": len(rows_by_trip),
            "average_stops_per_day": round(
                sum(len(seq) for seq in role_sequences) / len(role_sequences), 2
            ),
            "most_common_daily_role_order": list(most_common_sequence),
            "most_common_daily_role_order_support": support,
            "role_transitions": role_transitions,
            "note": (
                "실제 관광지 이름/숙소/하루 방문 개수는 포함하지 않음. "
                "여러 유사 여행에서 공통적으로 나타난 방문 순서·흐름만 참고."
            ),
        }

    def _collect_rag_candidates(
        self,
        condition: TravelCondition,
        *,
        top_k: int = RAG_CANDIDATE_POOL_TOP_K,
        extra_request: str | None = None,
    ) -> list[RetrievedPlace]:
        """"사용자가 원하는 장소는?"을 찾는다 (RAG 브랜치).

        여행 스타일(preferred_visit_types)과 자유 요청(must_visit_places 등)을
        하나의 검색어로 합쳐, role에 국한하지 않고 폭넓게 후보를 가져온다.
        """

        container = self._container
        query = container.llm_service.generate_style_query(condition)
        if extra_request:
            query = f"{query} {extra_request}".strip()

        response = container.retrieval_service.search_places(
            query,
            filters=PlaceSearchFilters(
                route_eligible=True,
                schedule_eligible=True,
            ),
            top_k=top_k,
        )
        return list(response.places)

    def _plan_slot_from_pool(
        self,
        condition: TravelCondition,
        *,
        day_no: int,
        slot_template: dict[str, Any],
        pool_by_role: dict[str, list[RetrievedPlace]],
        exclude_content_ids: set[int],
    ) -> ItinerarySlot:
        role = slot_template["role"]
        places = pool_by_role.get(role, [])

        candidates = select_candidates(
            places,
            condition,
            role=role,
            location_hint=slot_template.get("location_hint"),
            exclude_content_ids=exclude_content_ids,
            config=self._container.planner_config,
        )

        if not candidates:
            # 통합 후보 풀에 이 role의 후보가 없으면(드문 경우), 이 슬롯만
            # 예외적으로 즉석 검색해서 보강한다.
            print(
                f"[candidate-pool] day={day_no} role={role} 후보 0개 "
                "-> 즉석 검색으로 보강"
            )
            return self._search_and_plan_slot(
                condition,
                day_no=day_no,
                slot_template=slot_template,
                exclude_content_ids=exclude_content_ids,
            )

        return ItinerarySlot(
            day=day_no,
            sequence=slot_template["sequence"],
            role=role,
            target_collections=tuple(slot_template["target_collections"]),
            itinerary_roles=tuple(slot_template["itinerary_roles"]),
            stay_minutes=slot_template.get("stay_minutes"),
            location_hint=slot_template.get("location_hint"),
            query="candidate_pool(aihub+rag)",
            candidates=candidates,
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
        """Guarantee every ``TravelCondition.must_visit_places`` entry is
        offered to the LLM as a candidate, instead of leaving it to Planner's
        ranking (which has no way to know "the traveller named this place").

        Returns the slots that were actually modified, so callers can make
        sure those slots are included in the LLM prompt (initial generation
        already sends every slot; free-chat revision only sends changed
        slots, so it needs this list explicitly).
        """

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


def _bucket_by_role(pool: Sequence[RetrievedPlace]) -> dict[str, list[RetrievedPlace]]:
    """RAG 후보 풀을 슬롯 role별로 나눈다. (관광지 선택 규칙: 모든 관광지는
    RAG 검색 결과 안에서만 선택하므로, role에 맞는 부분집합만 골라 쓴다.)"""

    buckets: dict[str, list[RetrievedPlace]] = defaultdict(list)
    for place in pool:
        buckets[_infer_role_from_tags(place.tags)].append(place)
    return buckets


def _best_name_match(places: Sequence[RetrievedPlace], name: str) -> RetrievedPlace:
    """Prefer a result whose title actually contains the requested name;
    RAG similarity search can otherwise surface a merely-related place."""

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
    """Fallback day/slot skeleton used when no AIHub reference trip matches."""

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
