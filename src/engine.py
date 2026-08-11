from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Sequence

from .mappings.trip_feature_mapping import (
    SLOT_ITINERARY_ROLES,
    SLOT_TARGET_COLLECTIONS,
    get_visit_area_type_mapping,
)
from .aihub.similarity import AIHubPatternService, aggregate_role_keywords
from .common.env import load_env_file
from .llm import LLMService, create_llm_service
from .models import ItinerarySlot, ItineraryState, SlotAddRequest, SlotCandidate, TravelCondition, apply_delta, infer_affected_slots

from .planner import PlannerConfig, select_candidates
from .rag import PlaceSearchFilters, PlaceSearchService, create_place_search_service
from .rag.models import RetrievedPlace
from .recommender import create_pattern_service

DEFAULT_SEARCH_TOP_K = 30

# --- AIHub(이동 패턴) + RAG(관광지 후보) 조합 (초기 일정 생성) ---

# 각 모듈은 서로 다른 질문에 답한다:
#
# AIHub -> "비슷한 사람들은 어떻게 이동했는가?"
#         비슷한 여행자의 이동/방문 패턴을 참고자료로 제공
#
# RAG   -> "사용자가 원하는 스타일/자유 요청에 맞는 장소는 어디인가?"
#         실제 일정에 사용할 장소 후보군을 제공
#
# Planner -> "이번 여행에서 하루에 몇 개의 장소를 사용할 것인가?"
#           RAG 후보의 실제 가용성과 사용자의 pace를 기준으로
#           하루별 슬롯 수와 role을 동적으로 결정한다.
#
# 하루 슬롯 수는 AIHub 참고 여행의 평균 방문 수를 우선 사용하고,
# AIHub 참고 여행이 없으면 pace를 기준으로 하되 최소 5개를 보장한다.
# AIHub 이동 패턴은 최종 LLM이 일정 순서와 동선을 정할 때
# 참고자료로만 사용한다.

RAG_CANDIDATE_POOL_TOP_K = 100

# food(맛집)는 사용자의 style 문장에 잘 드러나지 않아 통합(broad) 검색 한 번으로는
# 후보 풀에 거의 섞여 들어오지 않는 경우가 많다. 그 결과 food 슬롯을 채울 때마다
# 후보 풀이 아니라 슬롯별 즉석 검색(_search_and_plan_slot)으로 계속 빠지게 된다.
# 이를 막기 위해 food 전용 검색을 후보 풀 수집 단계에서 한 번 더 돌려 합쳐준다.
FOOD_CANDIDATE_POOL_TOP_K = 40


# ------------------------------------------------------------
# 사용자 여행 속도별 하루 목표 방문 수
# ------------------------------------------------------------

_PACE_TARGET_STOPS_PER_DAY: dict[str, int] = {
    "relaxed": 5,
    "balanced": 5,
    "packed": 5,
}


# ------------------------------------------------------------
# 사용자 선호 유형 -> 우선적으로 사용할 일정 role
# ------------------------------------------------------------

_ROLE_PRIORITY_BY_PREFERENCE: dict[str, tuple[str, ...]] = {
    "nature": ("visit",),
    "history": ("visit",),
    "culture": ("visit",),
    "market_shopping": ("shopping", "visit"),
    "leisure": ("visit", "food"),
    "theme_park": ("activity",),
    "trail": ("visit",),
    "festival": ("visit",),
    "food_cafe": ("food",),
    "experience": ("activity",),
}


# ------------------------------------------------------------
# role별 기본 체류 시간
# ------------------------------------------------------------

_DEFAULT_STAY_MINUTES_BY_ROLE: dict[str, int] = {
    "visit": 90,
    "activity": 120,
    "food": 60,
    "shopping": 30,
}


# ------------------------------------------------------------
# RAG collection -> itinerary role
# ------------------------------------------------------------

_TARGET_COLLECTION_TO_ROLE: dict[str, str] = {
    "restaurants": "food",
    "shopping": "shopping",
    "activities": "activity",
    "attractions": "visit",
    "lodgings": "stay",
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

        # ------------------------------------------------------------
        # 1) 기본 여행 조건을 추출한다.
        #    슬롯 구조는 RAG 후보를 확인한 뒤
        #    사용자의 pace와 후보 가용성에 따라 동적으로 결정한다.
        #    하루 5개처럼 고정하지 않는다.
        # ------------------------------------------------------------

        # ------------------------------------------------------------
        # 1.5) AIHub Top-K 참고 여행과 방문 기록을 한 번만 조회해서,
        #      이동 패턴 요약(movement_patterns)과 role별 대표 키워드
        #      (reference_keywords)를 만드는 데 함께 사용한다. 같은
        #      travel_id 세트를 쓰는데 DB를 두 번 긁지 않기 위함이다.
        # ------------------------------------------------------------
        matches, routes = self._fetch_reference_trips_and_routes(condition)

        # ------------------------------------------------------------
        # 2) RAG: 실제로 슬롯에 채워 넣을 수 있는 유일한 관광지 후보군.
        #    role에 국한하지 않고 폭넓게 검색한 뒤, role별로 나눠 둔다.
        #    검색 쿼리는 사용자 조건 + AIHub 참고 키워드(reference_keywords)로
        #    보강한다. reference_keywords는 최종 후보가 아니라 검색 방향을
        #    보강하는 참고 자료일 뿐이며, 실제 후보는 항상 RAG 결과에서만 나온다.
        # ------------------------------------------------------------
        reference_keywords = aggregate_role_keywords(routes)
        rag_pool = self._collect_rag_candidates(
            condition, reference_keywords=reference_keywords
        )
        pool_by_role = _bucket_by_role(rag_pool)
        day_templates = _dynamic_day_structure(condition, pool_by_role, matches=matches)

        # ------------------------------------------------------------
        # 3) AIHub: 실제 장소 이름이 아니라, 여러 유사 여행에서 공통적으로
        #    나타나는 "이동 패턴"(방문 순서·흐름)만 요약해서 LLM 참고자료로
        #    전달한다. 특정 여행 하나를 그대로 따르지 않도록 top-K 여행을
        #    종합한다.
        # ------------------------------------------------------------
        movement_patterns = self._build_movement_pattern_context(
            condition, matches=matches, routes=routes
        )

        print("=" * 50)
        print(f"[candidate-pool] RAG 후보 {len(rag_pool)}개")
        for candidate in rag_pool:
            print(
                "[DEBUG CANDIDATE]",
                candidate.title,
                candidate.tags,
            )
        print(
            "[candidate-pool] role별 개수:",
            {role: len(places) for role, places in pool_by_role.items()},
        )
        print("[reference-keywords] AIHub 참고 키워드:", reference_keywords)
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
    # AIHub 이동 패턴 / RAG 후보군 조회
    # ------------------------------------------------------------------
    def _fetch_reference_trips_and_routes(
        self,
        condition: TravelCondition,
    ) -> tuple[list[Any], list[dict[str, Any]]]:
        """조건에 맞는 Top-K 참고 여행(matches)과 그 방문 기록(routes)을 한 번만
        조회한다. movement_patterns 계산과 reference_keywords 집계가 같은
        travel_id 세트를 쓰기 때문에, 이 결과를 두 곳에 함께 넘겨서 DB를
        중복으로 긁지 않도록 한다."""

        container = self._container
        matches = container.pattern_service.find_reference_trips(condition)
        if not matches:
            return [], []

        keyword_matches = (container.pattern_service.find_reference_keyword_trips(condition))
        if not keyword_matches:
            return matches, []

        travel_ids = [
            match.profile.travel_id
            for match in keyword_matches
        ]
        routes = container.pattern_service.repository.fetch_trip_routes(travel_ids)

        return matches, routes

    def _build_movement_pattern_context(
        self,
        condition: TravelCondition,
        *,
        matches: Sequence[Any] | None = None,
        routes: Sequence[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """AIHub 브랜치: "비슷한 사람들은 어떻게 이동했는가?"

        실제 관광지 이름, 숙소 위치, 하루 방문 개수, 일정 전체 구성은
        절대 포함하지 않는다. 특정 여행 하나를 그대로 따르지 않도록,
        동행/기간이 유사한 top-K 여행에서 공통적으로 나타나는
        "역할(role) 순서"와 "흐름(role -> role 전이)"만 집계해서
        LLM 참고자료로 돌려준다.

        ``matches``/``routes``를 넘기면 (예: ``create_itinerary``에서 이미
        조회한 결과) 재조회하지 않고 그대로 사용한다.
        """

        if matches is None or routes is None:
            matches, routes = self._fetch_reference_trips_and_routes(condition)
        if not matches:
            return {"available": False}

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
                roles = tuple(
                    mapping.slot_role
                    for row in ordered
                    if (
                        mapping := get_visit_area_type_mapping(
                            row.get("visit_area_type_cd")
                        )
                    ) is not None
                    and mapping.slot_role in SLOT_TARGET_COLLECTIONS
                )
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
        reference_keywords: dict[str, list[str]] | None = None,
    ) -> list[RetrievedPlace]:
        """사용자가 원하는 장소는?을 찾는다 (RAG 브랜치).

        여행 스타일(preferred_visit_types)과 자유 요청(must_visit_places 등)을
        하나의 검색어로 합쳐, role에 국한하지 않고 폭넓게 후보를 가져온다.

        ``reference_keywords``가 있으면(Top-K AIHub 참고 여행에서 뽑은 role별
        대표 방문 장소명) 검색어 생성 프롬프트에 참고 자료로 함께 전달한다.
        이 키워드는 검색 방향을 보강할 뿐, 그대로 후보에 들어가지는 않는다.
        실제 후보는 항상 이 검색으로 얻은 RAG 결과에서만 선택된다.
        """

        container = self._container

        query = container.llm_service.generate_style_query(
            condition,
            reference_keywords=reference_keywords,
        )

        if extra_request:
            query = f"{query} {extra_request}".strip()

        response = container.retrieval_service.search_places(
            query,
            filters=PlaceSearchFilters(
                recommendation_scopes=("default",),
                route_eligible=True,
                schedule_eligible=True,
            ),
            top_k=top_k,
        )

        places = list(response.places)

        # 일반 생활형 매장/브랜드 매장 제거
        places = [
            place
            for place in places
            if (
                not any(
                    tag.startswith("target_collection:shopping")
                    for tag in place.tags
                )
                or _is_valid_shopping_candidate(place)
            )
        ]

        print("=" * 80)
        print("[SHOPPING DEBUG] RAG 후보 분류 확인")

        for place in places:
            if any(
                tag.startswith("target_collection:shopping")
                for tag in place.tags
            ):
                print(
                    "[SHOPPING]",
                    "content_id=",
                    place.content_id,
                    "title=",
                    place.title,
                    "tags=",
                    place.tags,
                )

        print("=" * 80)

        # ------------------------------------------------------------
        # food(맛집) 전용 보강 검색
        #
        # 통합 검색은 style/must_visit_places 위주라 restaurants가
        # 후보 풀에 거의 섞이지 않는 경우가 있다.
        # food도 처음부터 후보 풀에 확보한다.
        # ------------------------------------------------------------
        food_query = container.llm_service.generate_search_query(
            condition,
            slot_role="food",
            day=1,
            extra_request=extra_request,
        )

        food_response = container.retrieval_service.search_places(
            food_query,
            filters=PlaceSearchFilters(
                target_collections=("restaurants",),
                route_eligible=True,
                schedule_eligible=True,
            ),
            top_k=FOOD_CANDIDATE_POOL_TOP_K,
        )

        existing_ids = {
            place.content_id
            for place in places
        }

        for place in food_response.places:
            if place.content_id not in existing_ids:
                places.append(place)
                existing_ids.add(place.content_id)

        return places

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
            condition,
            slot_role=role,
            day=day_no,
            extra_request=extra_request,
        )

        filters = PlaceSearchFilters(
            target_collections=tuple(slot_template["target_collections"]),
            itinerary_roles=tuple(slot_template["itinerary_roles"]),
            route_eligible=True,
            schedule_eligible=True,
        )

        response = container.retrieval_service.search_places(
            query,
            filters=filters,
            top_k=DEFAULT_SEARCH_TOP_K,
        )

        search_places = list(response.places)

        if role == "shopping":
            search_places = [
                place
                for place in search_places
                if _is_valid_shopping_candidate(place)
            ]

        candidates = select_candidates(
            search_places,
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

def _is_valid_shopping_candidate(place: RetrievedPlace) -> bool:
    """여행 일정용 쇼핑 장소인지 판단한다."""

    tags = set(place.tags or ())
    title = (place.title or "").lower()

    # 시장은 허용
    if "place_subtype:market" in tags:
        return True

    # 특산품/기념품점은 허용
    if "place_subtype:local_specialty" in tags:
        return True

    # general_retail이 아니면 허용
    if "place_subtype:general_retail" not in tags:
        return True

    # 여행 목적의 쇼핑점은 허용
    allowed_keywords = (
        "특산품",
        "기념품",
        "선물",
        "토산품",
        "소품샵",
        "소품",
    )

    if any(keyword in title for keyword in allowed_keywords):
        return True

    # 일반 생활형 / 브랜드 매장은 제외
    excluded_keywords = (
        "마트",
        "이마트",
        "하나로",
        "올리브영",
        "이니스프리",
        "다이소",
        "탑텐",
        "쌤소나이트",
        "내셔널지오그래픽",
        "유니클로",
        "나이키",
        "아디다스",
        "아울렛",
    )

    if any(keyword in title for keyword in excluded_keywords):
        return False

    # general_retail인데 관광 목적 쇼핑이라는 근거가 없으면 제외
    return False


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


def _dynamic_day_structure(
    condition: TravelCondition,
    pool_by_role: dict[str, list[RetrievedPlace]],
    *,
    matches: Sequence[Any] | None = None,
) -> list[dict[str, Any]]:
    """
    하루 슬롯 개수를 "5개 고정"이나 pace 조견표로 정하지 않고,
    min_usable_visits(>=5) 필터를 통과한 AIHub 참고 여행자들의
    실제 하루 평균 방문 개수(stops_per_day)를 기준으로 정한다.

    - matches가 있으면: 참고 여행자들의 stops_per_day 평균을 사용한다.
    - matches가 없으면: pace를 사용하되 최소 5개를 보장한다.

    두 경우 모두, 실제 RAG 후보 가용성보다 많은 슬롯을 만들지는 않는다.
    """

    total_days = max(condition.duration_days, 1)

    total_candidates = sum(
        len(places)
        for places in pool_by_role.values()
    )

    target_per_day = _target_stops_per_day_from_matches(matches)

    if target_per_day is None:
        # 참고할 AIHub 여행자가 하나도 없을 때만 pace로 폴백한다.
        pace = (
            condition.pace.value
            if condition.pace is not None
            else "balanced"
        )
        target_per_day = _PACE_TARGET_STOPS_PER_DAY.get(
            pace,
            _PACE_TARGET_STOPS_PER_DAY["balanced"],
        )
    target_per_day = max(5, target_per_day)

    if total_candidates > 0:
        available_per_day = max(
            1,
            total_candidates // total_days,
        )

        target_per_day = min(
            target_per_day,
            available_per_day,
        )
    else:
        target_per_day = 1

    target_per_day = max(1, target_per_day)

    days: list[dict[str, Any]] = []

    for day_no in range(1, total_days + 1):
        roles = _choose_dynamic_roles(
            condition,
            pool_by_role,
            count=target_per_day,
        )

        slots = []

        for sequence, role in enumerate(roles, start=1):
            slots.append(
                {
                    "sequence": sequence,
                    "role": role,
                    "target_collections": list(
                        SLOT_TARGET_COLLECTIONS.get(role, ())
                    ),
                    "itinerary_roles": list(
                        SLOT_ITINERARY_ROLES.get(role, ())
                    ),
                    "stay_minutes": _DEFAULT_STAY_MINUTES_BY_ROLE.get(
                        role,
                        90,
                    ),
                    "location_hint": None,
                }
            )

        days.append(
            {
                "day": day_no,
                "region": None,
                "slot_count": len(slots),
                "slots": slots,
            }
        )

        print(
            f"[dynamic-slots] day={day_no} "
            f"slot_count={len(slots)} "
            f"roles={roles}"
        )

    return days

def _target_stops_per_day_from_matches(
    matches: Sequence[Any] | None,
) -> int | None:
    """min_usable_visits(>=5) 필터를 통과한 참고 여행자들의
    stops_per_day(방문개수/기간) 평균을 반올림해서 반환한다.
    참고 여행자가 없으면 None을 반환해서 pace 폴백을 쓰게 한다."""

    if not matches:
        return None

    stops_per_day_values = [
        match.profile.stops_per_day
        for match in matches
        if getattr(match, "profile", None) is not None
    ]

    if not stops_per_day_values:
        return None

    average = sum(stops_per_day_values) / len(stops_per_day_values)

    return max(1, round(average))


def _choose_dynamic_roles(
    condition: TravelCondition,
    pool_by_role: dict[str, list[RetrievedPlace]],
    *,
    count: int,
) -> list[str]:
    """사용자 선호와 실제 RAG 후보를 기준으로 하루 role을 구성한다.

    한 role이 하루 슬롯을 독식하지 않도록, 선호 role 목록을 라운드로빈으로
    돌면서 한 번에 하나씩만 배정한다. 예전에는 "아직 후보가 안 바닥난
    role이면 무조건 그 role"이라서, 후보가 많은 role(예: activity) 하나가
    하루 슬롯을 전부 차지하고 food/visit는 후보가 있어도 한 번도 선택되지
    못하는 문제가 있었다.
    """

    if count <= 0:
        return []

    available_counts = {
        role: len(places)
        for role, places in pool_by_role.items()
        if places
    }

    if not available_counts:
        # 후보가 전혀 없을 때도 "visit" 하드코딩이 아니라, 사용자가
        # 원한 role을 그대로 돌려준다. 그마저 없으면 최후 수단으로 visit.
        for preference in condition.preferred_visit_types:
            roles_for_preference = _ROLE_PRIORITY_BY_PREFERENCE.get(
                preference.value, ()
            )
            if roles_for_preference:
                return [roles_for_preference[0]] * count
        return ["visit"] * count

    preferred_roles: list[str] = []

    # 사용자 선호를 먼저 반영
    for preference in condition.preferred_visit_types:
        for role in _ROLE_PRIORITY_BY_PREFERENCE.get(
            preference.value,
            (),
        ):
            if role not in preferred_roles:
                preferred_roles.append(role)

    # 기본 우선순위
    for role in (
        "visit",
        "food",
        "activity",
        "shopping",
    ):
        if role in available_counts and role not in preferred_roles:
            preferred_roles.append(role)

    # 후보가 실제로 있는 role만 라운드로빈 대상으로 남긴다
    preferred_roles = [
        role for role in preferred_roles if available_counts.get(role, 0) > 0
    ]

    if not preferred_roles:
        return ["visit"] * count

    # 하루 food는 기본적으로 1개로 제한한다 (여러 끼를 몰아넣지 않도록)
    role_caps = dict(available_counts)
    if "food" in role_caps:
        role_caps["food"] = min(role_caps["food"], 1)

    roles: list[str] = []
    used_by_role: Counter[str] = Counter()

    while len(roles) < count:
        progressed = False

        for role in preferred_roles:
            if len(roles) >= count:
                break

            if used_by_role[role] >= role_caps.get(role, 0):
                continue

            roles.append(role)
            used_by_role[role] += 1
            progressed = True

        if not progressed:
            # 모든 role의 후보를 소진했으면 더 배정할 게 없다
            break

    # 아직 목표 개수보다 부족하면 남은 후보가 많은 role 사용
    while len(roles) < count:
        remaining_roles = [
            role
            for role, available in available_counts.items()
            if used_by_role[role] < available
        ]

        if not remaining_roles:
            break

        selected_role = max(
            remaining_roles,
            key=lambda role: (
                available_counts[role]
                - used_by_role[role]
            ),
        )

        roles.append(selected_role)
        used_by_role[selected_role] += 1

    return roles