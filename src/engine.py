from __future__ import annotations

import copy
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass, field, replace
from pathlib import Path
import re
from typing import Any, Sequence

from .mappings.trip_feature_mapping import (
    SLOT_ITINERARY_ROLES,
    SLOT_TARGET_COLLECTIONS,
    get_region_districts,
    get_visit_area_type_mapping,
)
from .aihub.similarity import AIHubPatternService, aggregate_role_keywords
from .common.env import load_env_file
from .common.geo import haversine_km
from .llm import LLMService, create_llm_service
from .models import ConditionDelta, ItinerarySlot, ItineraryState, SlotAddRequest, SlotCandidate, TravelCondition, apply_delta, infer_affected_slots

from .planner import PlannerConfig, select_candidates
from .rag import PlaceSearchFilters, PlaceSearchService, create_place_search_service
from .rag.models import RetrievedPlace
from .recommender import MySQLPackageRepository, PackageRecommendationService, create_pattern_service
from .config.settings import MySQLConfig

DEFAULT_SEARCH_TOP_K = 15

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
SHOPPING_CANDIDATE_POOL_TOP_K = 30
ACTIVITY_CANDIDATE_POOL_TOP_K = 30

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
_DELETE_REQUEST_RE = re.compile(r"삭제|제거|지워|지우|빼")
_DAY_POSITION_RE = re.compile(r"(\d+)\s*(?:일차|째\s*날)")
_SEQUENCE_POSITION_RE = re.compile(
    r"(?:(\d+)|(?P<word>첫|두|둘|세|셋|네|넷|다섯))\s*번째"
)
_KOREAN_ORDINALS = {
    "첫": 1,
    "두": 2,
    "둘": 2,
    "세": 3,
    "셋": 3,
    "네": 4,
    "넷": 4,
    "다섯": 5,
}

@dataclass
class ChatUpdateResult:
    """자유채팅 한 턴을 처리한 결과.

    mode="recommend" 일 때는 itinerary/state가 전혀 바뀌지 않는다. 사용자가
    아직 "적용해줘"라고 말하지 않았기 때문에, 후보만 보여주고 실제 일정은
    건드리지 않는 것이 이 클래스가 존재하는 이유다.

    mode="edit" 일 때는 state가 실제로 갱신된 새 ItineraryState를 담는다.

    mode="no_change" 일 때는 사용자의 메시지에서 아무 변경 신호도 찾지 못한
    경우다 (기존 delta.is_empty() 케이스).
    """

    mode: str
    state: ItineraryState
    message: str = ""
    recommendations: list[dict[str, Any]] = field(default_factory=list)
    locked_days: tuple[int, ...] = ()

    @property
    def condition(self) -> TravelCondition:
        return self.state.condition

    @property
    def slots(self) -> list[ItinerarySlot]:
        return self.state.slots

    @property
    def itinerary(self) -> dict[str, Any]:
        return self.state.itinerary

    @property
    def used_content_ids(self) -> set[int]:
        return self.state.used_content_ids


@dataclass(frozen=True)
class AppContainer:
    retrieval_service: PlaceSearchService
    pattern_service: AIHubPatternService
    llm_service: LLMService
    planner_config: PlannerConfig
    package_service: PackageRecommendationService | None = None


def create_container(
    project_root: str | Path,
    *,
    planner_config: PlannerConfig | None = None,
) -> AppContainer:
    project_root = Path(project_root)
    load_env_file(project_root / ".env")

    retrieval_service = create_place_search_service(
        project_root=project_root
    )

    pattern_service = create_pattern_service(
        project_root=project_root
    )

    mysql_config = MySQLConfig.from_env()

    package_service = PackageRecommendationService(
        MySQLPackageRepository(mysql_config)
    )

    llm_service = create_llm_service()

    return AppContainer(
        retrieval_service=retrieval_service,
        pattern_service=pattern_service,
        llm_service=llm_service,
        package_service=package_service,
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

        rag_pool = self._collect_rag_candidates(condition, reference_keywords=reference_keywords)
        pool_by_role = _bucket_by_role(rag_pool)
        movement_patterns = self._build_movement_pattern_context(condition, matches=matches, routes=routes)
        day_templates = _dynamic_day_structure(condition, pool_by_role, matches=matches, movement_patterns=movement_patterns)
        # ------------------------------------------------------------
        # 3) AIHub: 실제 장소 이름이 아니라, 여러 유사 여행에서 공통적으로
        #    나타나는 "이동 패턴"(방문 순서·흐름)만 요약해서 LLM 참고자료로
        #    전달한다. 특정 여행 하나를 그대로 따르지 않도록 top-K 여행을
        #    종합한다.
        # ------------------------------------------------------------
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
            recommendations=[],
        )
    # ------------------------------------------------------------------
    # Free-chat modification
    # ------------------------------------------------------------------
    def update_itinerary_from_chat(
        self, state: ItineraryState, user_text: str
    ) -> ChatUpdateResult:
        container = self._container
        delta = container.llm_service.extract_condition_delta(state.condition, user_text)

        position_delete = _parse_position_delete_request(user_text)
        base_slots = state.slots
        base_itinerary = state.itinerary
        base_used_content_ids = set(state.used_content_ids)
        new_condition = None

        if delta.remove_places or position_delete is not None:
            new_condition = apply_delta(state.condition, delta)
            (
                base_slots,
                base_itinerary,
                base_used_content_ids,
                removed_titles,
            ) = _remove_schedule_entries(
                state,
                titles=delta.remove_places,
                position=position_delete,
            )
            if removed_titles:
                new_condition = apply_delta(
                    new_condition,
                    ConditionDelta(add_excluded_places=removed_titles),
                )

            remaining_delta = (
                ConditionDelta()
                if position_delete is not None
                else replace(delta, remove_places=(), notes="")
            )
            if remaining_delta.is_empty():
                return ChatUpdateResult(
                    mode="edit",
                    state=ItineraryState(
                        condition=new_condition,
                        slots=base_slots,
                        itinerary=base_itinerary,
                        used_content_ids=base_used_content_ids,
                        recommendations=state.recommendations,
                    ),
                    message="일정을 수정했어요.",
                )
            delta = remaining_delta

        if delta.is_empty():
            print("[revise] delta.is_empty() == True -> 변경할 내용 없음, 그대로 반환")
            return ChatUpdateResult(
                mode="no_change",
                state=ItineraryState(
                    condition=state.condition,
                    slots=state.slots,
                    itinerary=state.itinerary,
                    used_content_ids=set(state.used_content_ids),
                    recommendations=state.recommendations,
                ),
            )

        # --------------------------------------------------------------
        # recommend 모드: 일정은 절대 건드리지 않고, 후보 몇 개만 채팅으로
        # 보여준다. "여기 수정해줘" 같은 실제 편집 요청과는 완전히 분리된
        # 경로이므로, 여기서는 state를 그대로 두고 반환한다.
        # --------------------------------------------------------------
        if delta.mode == "recommend":
            print("[revise] mode == recommend -> 일정 미변경, 후보만 조회")
            recommendations = self._build_route_aware_recommendations(
                state,
                delta,
                user_text,
            )
            next_state = ItineraryState(
                condition=state.condition,
                slots=state.slots,
                itinerary=state.itinerary,
                used_content_ids=set(state.used_content_ids),
                recommendations=recommendations,
            )
            return ChatUpdateResult(
                mode="recommend",
                state=next_state,
                message=_build_recommend_message(delta, recommendations),
                recommendations=recommendations,
            )

        if new_condition is None:
            new_condition = apply_delta(state.condition, delta)
        print("[revise] state.recommendations:", state.recommendations)
        print("[revise] delta.add_must_visit_places:", delta.add_must_visit_places)
       # --------------------------------------------------------------
        # 장소 선택/교체 요청 처리
        #
        # 1) 최근 추천 후보에 있으면 그대로 사용
        # 2) 최근 추천 후보에 없더라도
        #    "A 말고 B로 변경"처럼 장소명이 명확하면
        #    B만 1회 검색해서 사용
        #
        # 핵심:
        # 전체 슬롯 재검색은 하지 않는다.
        # --------------------------------------------------------------
        if delta.add_must_visit_places:

            recommended_place = None

            # ----------------------------------------------------------
            # 1. 최근 추천 후보에서 먼저 찾는다.
            # ----------------------------------------------------------
            if state.recommendations:
                for place_name in delta.add_must_visit_places:
                    recommended_place = _find_recommended_place(
                        state.recommendations,
                        place_name,
                    )

                    if recommended_place:
                        print(
                            "[revise] 최근 추천 후보 사용:",
                            recommended_place.get("title"),
                        )
                        break

            # ----------------------------------------------------------
            # 2. 추천 후보에 없으면 요청한 장소만 1회 검색한다.
            #
            # 예:
            # "일출랜드를 섭지코지로 변경해줘"
            #
            # → 섭지코지만 검색
            # → 기존 1일차 전체 슬롯 재검색 X
            # ----------------------------------------------------------
            if recommended_place is None:
                replacement_name = (
                    delta.add_must_visit_places[0]
                )

                print(
                    "[revise] 추천 후보에 없음 -> 교체 장소만 검색:",
                    replacement_name,
                )

                response = container.retrieval_service.search_places(
                    replacement_name,
                    filters=PlaceSearchFilters(
                        recommendation_scopes=("default",),
                        route_eligible=True,
                        schedule_eligible=True,
                        region_pairs=get_region_districts(new_condition.region),
                    ),
                    top_k=3,
                )

                if response.places:
                    replacement_place = _best_name_match(
                        response.places,
                        replacement_name,
                    )

                    if replacement_place is not None:
                        recommended_place = _candidate_to_recommendation(
                            SlotCandidate(
                                content_id=replacement_place.content_id,
                                title=replacement_place.title,
                                final_score=1.0,
                                similarity_score=getattr(
                                    replacement_place,
                                    "similarity_score",
                                    None,
                                ),
                                place=replacement_place.to_dict(),
                                forced=True,
                            )
                        )

                        print(
                            "[revise] 직접 검색한 교체 후보:",
                            recommended_place["title"],
                            recommended_place["content_id"],
                        )

            # ----------------------------------------------------------
            # 3. 장소를 확보했으면 기존 일반 edit 로직으로 내려가지 않고
            #    바로 추가/교체 처리한다.
            # ----------------------------------------------------------
            if recommended_place:
                return self._apply_recommended_place(
                    state=state,
                    new_condition=new_condition,
                    recommendation=recommended_place,
                    target_day=delta.target_day,
                    remove_places=(
                        delta.remove_must_visit_places
                        or delta.add_excluded_places
                    ),
                    role_hint=(
                        delta.affected_slots[0]
                        if delta.affected_slots
                        else None
                    ),
                    user_text=user_text,
                    insert_after=delta.insert_after,
                    insert_before=delta.insert_before,
                    time_period=delta.time_period,
                )

            if delta.remove_must_visit_places:
                recommendations = self._build_chat_recommendations(
                    state,
                    delta,
                    user_text,
                    location_hint=_location_hint_for_day(
                        state,
                        delta.target_day,
                    ),
                )
                return ChatUpdateResult(
                    mode="recommend",
                    state=ItineraryState(
                        condition=state.condition,
                        slots=state.slots,
                        itinerary=state.itinerary,
                        used_content_ids=set(state.used_content_ids),
                        recommendations=recommendations,
                    ),
                    message=(
                        f"'{delta.add_must_visit_places[0]}'을(를) 찾지 못했어요. "
                        "대신 근처 후보를 찾아봤어요."
                    ),
                    recommendations=recommendations,
                )

        affected_roles = set(infer_affected_slots(delta))
        print("[revise] affected_roles :", affected_roles)

        # ----------------------------------------------------------------
        # "여기(이 부분)만 수정해줘" 같은 요청이 일정 전체로 번지지 않도록,
        # 가능하면 영향 범위를 특정 day/특정 stop으로 좁힌다. 좁힐 수 있는
        # 근거(특정 일차 언급, 실제 일정에 있는 장소명 언급)가 전혀 없을
        # 때만 role 전체(모든 day)를 대상으로 삼는다.
        # ----------------------------------------------------------------
        scoped_keys = _scope_affected_keys(state, delta)
        print("[revise] scoped_keys (None이면 role 전체 대상):", scoped_keys)

        used_content_ids = base_used_content_ids
        updated_slots: list[ItinerarySlot] = []
        re_searched_keys: set[tuple[int, int]] = set()

        for slot in base_slots:
            if slot.role not in affected_roles:
                updated_slots.append(slot)
                continue

            if scoped_keys is not None and (slot.day, slot.sequence) not in scoped_keys:
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
            new_condition, updated_slots, used_content_ids, target_day=delta.target_day)

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
                new_condition, base_itinerary, changed_slot_payloads
            )
            # LLM이 프롬프트 지시를 어기고 changed_keys 밖의 stop을 건드렸더라도
            # 최종 결과에서는 무조건 원본 그대로 되돌린다 (코드 레벨 강제).
            itinerary = _enforce_revision_scope(base_itinerary, itinerary, changed_keys)
        else:
            print("[revise] changed_slot_payloads가 비어있어서 LLM 재구성 없이 그대로 반환")
            itinerary = base_itinerary

        return ChatUpdateResult(
            mode="edit",
            state=ItineraryState(
                condition=new_condition,
                slots=updated_slots,
                itinerary=itinerary,
                used_content_ids=used_content_ids,
                recommendations=state.recommendations,
            ),
            message="일정을 수정했어요.",
        )

    # ------------------------------------------------------------------
    # Free-chat "recommend only" (일정 미반영, 채팅에만 후보 노출)
    # ------------------------------------------------------------------
    def _build_chat_recommendations(
        self,
        state: ItineraryState,
        delta: ConditionDelta,
        user_text: str,
        *,
        limit: int = 3,
        location_hint: dict[str, float] | None = None,
    ) -> list[dict[str, Any]]:
        affected_roles = list(dict.fromkeys(infer_affected_slots(delta)))
        role = affected_roles[0] if affected_roles else "food"

        day_no = delta.target_day or 1
        slot_template = {
            "sequence": 0,
            "role": role,
            "target_collections": list(SLOT_TARGET_COLLECTIONS.get(role, ())),
            "itinerary_roles": list(SLOT_ITINERARY_ROLES.get(role, ())),
            "stay_minutes": _DEFAULT_STAY_MINUTES_BY_ROLE.get(role),
            "location_hint": location_hint,
        }

        condition_for_search = apply_delta(state.condition, delta)

        slot = self._search_and_plan_slot(
            condition_for_search,
            day_no=day_no,
            slot_template=slot_template,
            exclude_content_ids=set(state.used_content_ids),
            extra_request=(delta.notes or user_text or None),
        )
        recommendations = [
            _candidate_to_recommendation(c)
            for c in slot.candidates[:limit]
        ]

        print("[chat-recommend] 검색 후보")
        for i, recommendation in enumerate(recommendations, start=1):
            print(
                f"[{i}] {recommendation['title']} "
                f"(content_id={recommendation['content_id']})"
            )
            print(f"    summary={recommendation['summary']}")
            print(f"    address={recommendation['address']}")
            print(f"    thumbnail={recommendation['thumbnail']}")

        return recommendations

    # ------------------------------------------------------------------
    # AIHub 이동 패턴 / RAG 후보군 조회
    # ------------------------------------------------------------------
    def _fetch_reference_trips_and_routes(
        self,
        condition: TravelCondition,
    ) -> tuple[list[Any], list[dict[str, Any]]]:
        """AIHub 참고 경로를 우선 조회하고,
        없으면 패키지 경로를 fallback으로 사용한다.
        """

        container = self._container

        # ------------------------------------------------------------
        # 1차: AIHub 참고 여행 조회
        # ------------------------------------------------------------
        matches = container.pattern_service.find_reference_trips(condition)

        if matches:
            keyword_matches = (
                container.pattern_service.find_reference_keyword_trips(condition)
            )

            if keyword_matches:
                travel_ids = [
                    match.profile.travel_id
                    for match in keyword_matches
                ]

                routes = (
                    container.pattern_service.repository.fetch_trip_routes(
                        travel_ids
                    )
                )

                if routes:
                    print(
                        "[reference-route] "
                        f"AIHub 경로 사용: "
                        f"travel={len(travel_ids)}, routes={len(routes)}"
                    )

                    return matches, routes

        # ------------------------------------------------------------
        # 2차: AIHub 경로가 없으면 패키지 경로 fallback
        # ------------------------------------------------------------
        if container.package_service is None:
            return matches, []

        package_routes = container.package_service.find_reference_routes(
            condition,
            top_k=10,
        )

        if package_routes:

            print("[package-route-debug]")
            for row in package_routes:
                print(
                    f"package={row.get('package_id')} "
                    f"day={row.get('day_no')} "
                    f"seq={row.get('visit_order')} "
                    f"type={row.get('visit_area_type_cd')} "
                    f"name={row.get('place_name')}"
                )

            package_count = len(
                {
                    row["package_id"]
                    for row in package_routes
                }
            )

            print(
                "[reference-route] "
                "AIHub 경로 없음 -> 패키지 경로 fallback: "
                f"packages={package_count}, "
                f"routes={len(package_routes)}"
            )

            return [], package_routes

        # ------------------------------------------------------------
        # 3차: 참고 경로가 아예 없는 경우
        # ------------------------------------------------------------
        print(
            "[reference-route] "
            "AIHub/패키지 참고 경로 모두 없음"
        )

        return [], []

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

        if not routes:
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

        # 단일 역할 하루보다 실제 이동 흐름이 있는
        # 다중 역할 패턴을 우선해서 참고 패턴으로 사용한다.
        multi_role_sequences = {
            sequence: count
            for sequence, count in sequence_counts.items()
            if len(sequence) >= 2
        }

        if multi_role_sequences:
            pattern_counts = Counter(multi_role_sequences)
        else:
            pattern_counts = sequence_counts

        common_patterns = [
            {
                "role_order": list(sequence),
                "support": count,
            }
            for sequence, count in pattern_counts.most_common(5)
        ]

        most_common_sequence, support = pattern_counts.most_common(1)[0]

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

            # 가장 대표적인 다중 역할 패턴
            "most_common_daily_role_order": list(most_common_sequence),
            "most_common_daily_role_order_support": support,

            # 대표 패턴 하나에 묻히지 않도록 상위 패턴들을 함께 제공
            "common_daily_role_orders": common_patterns,

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
                region_pairs=get_region_districts(condition.region),
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
        if not any(_infer_role_from_tags(place.tags) == "food" for place in places):
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
                    region_pairs=get_region_districts(condition.region),
                ),
                top_k=FOOD_CANDIDATE_POOL_TOP_K,
            )

            existing_ids = {place.content_id for place in places}
            for place in food_response.places:
                if place.content_id not in existing_ids:
                    places.append(place)
                    existing_ids.add(place.content_id)

        shopping_requested = any(
            "shopping" in _ROLE_PRIORITY_BY_PREFERENCE.get(preference.value, ())
            for preference in condition.preferred_visit_types
        )
        has_shopping_candidate = any(
            _infer_role_from_tags(place.tags) == "shopping"
            for place in places
        )
        if shopping_requested and not has_shopping_candidate:
            shopping_query = container.llm_service.generate_search_query(
                condition,
                slot_role="shopping",
                day=1,
                extra_request=extra_request,
            )

            shopping_response = container.retrieval_service.search_places(
                shopping_query,
                filters=PlaceSearchFilters(
                    target_collections=("shopping",),
                    route_eligible=True,
                    schedule_eligible=True,
                    region_pairs=get_region_districts(condition.region),
                ),
                top_k=SHOPPING_CANDIDATE_POOL_TOP_K,
            )

            existing_ids = {place.content_id for place in places}
            for place in shopping_response.places:
                if (
                    place.content_id not in existing_ids
                    and _is_valid_shopping_candidate(place)
                ):
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
            region_pairs=get_region_districts(condition.region),
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

    def _build_route_aware_recommendations(
        self,
        state: ItineraryState,
        delta: ConditionDelta,
        user_text: str,
        *,
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        """`_build_chat_recommendations()`를 "동선 인지" 버전으로 감싼다.

        예전에는 "day 전체 stop 좌표 평균"을 기준점으로 근처 후보를
        찾았다. 그러면 1일차 2번째 슬롯(카페)을 바꾸려는데, 6번째
        슬롯 근처의 카페가 "평균 위치와 가깝다"는 이유로 추천될 수
        있었다 - 사용자가 원하는 "① -> 후보 -> ③" 동선과는 무관한
        기준이었다.

        여기서는:
        1) delta.remove_must_visit_places로 "바꾸려는 대상"이 기존
           일정의 어느 (day, sequence)인지 먼저 찾는다.
        2) 그 슬롯을 알면, 슬롯의 바로 앞/뒤 장소를 기준점으로 검색하고
           (_anchor_location_hint), 결과도 그 앞/뒤 장소 사이 우회
           거리로 다시 정렬한다 (_rerank_recommendations_by_route).
        3) 특정 슬롯을 모르면(예: "1일차 카페 추천해줘") day 전체를
           기준으로 하되, 정렬은 "그 day 어딘가에 넣었을 때 가장 우회가
           적은 위치" 기준으로 한다.
        """

        target_key: tuple[int, int] | None = None
        replace_places = (
            delta.remove_must_visit_places
            or delta.add_excluded_places
        )
        if replace_places:
            target_key = _find_stop_key_by_name(
                state,
                replace_places[0],
                delta.target_day,
            )

        anchor_day = target_key[0] if target_key else delta.target_day
        anchor_sequence = target_key[1] if target_key else None

        location_hint = _anchor_location_hint(state, anchor_day, anchor_sequence)

        recommendations = self._build_chat_recommendations(
            state,
            delta,
            user_text,
            limit=limit,
            location_hint=location_hint,
        )

        return _rerank_recommendations_by_route(
            recommendations,
            state=state,
            day_no=anchor_day,
            target_sequence=anchor_sequence,
        )

    def _apply_recommended_place(
        self,
        *,
        state: ItineraryState,
        new_condition: TravelCondition,
        recommendation: dict[str, Any],
        target_day: int | None,
        remove_places: Sequence[str] = (),
        role_hint: str | None = None,
        user_text: str = "",
        insert_after: str | None = None,
        insert_before: str | None = None,
        time_period: str | None = None,
    ) -> ChatUpdateResult:
        """
        최근 추천 후보를 다시 검색하지 않고 기존 일정에 직접 반영한다.

        1. remove_places가 있으면:
        기존 일정에서 해당 장소를 찾아 추천 장소로 교체한다.

        2. remove_places가 없으면:
        - insert_after/insert_before(장소 기준) 또는 time_period(시간대
          기준)가 지정되어 있고, 그 기준을 실제 일정에서 찾을 수 있으면
          해당 위치에 정확히 끼워넣고 그 day의 순서(sequence)를 코드
          레벨에서 강제로 재배열한다 (LLM에게 순서 판단을 맡기지 않는다).
        - 위치 기준이 없거나 찾지 못하면 기존 방식대로 지정된 날짜의
          마지막 슬롯 뒤에 추천 장소를 새로 추가한다.
        """

        title = str(
            recommendation.get("title") or ""
        ).strip()

        content_id = recommendation.get("content_id")

        if not title or content_id is None:
            return ChatUpdateResult(
                mode="no_change",
                state=state,
                message="추천 장소 정보를 찾지 못했어요.",
            )

        # ------------------------------------------------------------
        # 추천 후보의 role
        #
        # recommendation에는 현재 tags가 없을 수 있으므로
        # 교체 대상 슬롯의 role을 우선 사용한다.
        # ------------------------------------------------------------
        role = role_hint or "visit"

        # ------------------------------------------------------------
        # 기존 state를 직접 수정하지 않도록 복사
        # ------------------------------------------------------------
        updated_slots = copy.deepcopy(state.slots)
        position_locked_day: int | None = None

        # ============================================================
        # 1) 교체 모드
        # ============================================================
        if remove_places:
            normalized_remove_names = {
                _normalize_title(place_name)
                for place_name in remove_places
                if place_name
            }

            replacement_slot = None

            # --------------------------------------------------------
            # 기존 "최종 일정"에서 실제로 선택된 장소를 먼저 찾는다.
            #
            # 중요:
            # slot.candidates에는 후보가 여러 개 있을 수 있으므로
            # candidates를 먼저 보면 잘못된 슬롯을 잡을 수 있다.
            # --------------------------------------------------------
            stops_by_key = _itinerary_stops_by_key(
                state.itinerary
            )

            replacement_slot = None

            for (day_no, sequence), stop in stops_by_key.items():

                # target_day가 지정된 경우 해당 날짜만 확인
                if (
                    target_day is not None
                    and day_no != target_day
                ):
                    continue

                stop_title = _normalize_title(
                    str(stop.get("title") or "")
                )

                if any(
                    remove_name
                    and (
                        remove_name in stop_title
                        or stop_title in remove_name
                    )
                    for remove_name in normalized_remove_names
                ):
                    replacement_slot = next(
                        (
                            slot
                            for slot in updated_slots
                            if (
                                slot.day == day_no
                                and slot.sequence == sequence
                            )
                        ),
                        None,
                    )

                    if replacement_slot is not None:
                        break

            # --------------------------------------------------------
            # 최종 itinerary에서 못 찾은 경우에만
            # 기존 후보(candidate) 목록을 fallback으로 사용
            # --------------------------------------------------------
            if replacement_slot is None:
                for slot in updated_slots:
                    if (
                        target_day is not None
                        and slot.day != target_day
                    ):
                        continue

                    for candidate in slot.candidates:
                        candidate_title = _normalize_title(
                            candidate.title
                        )

                        if any(
                            remove_name
                            and (
                                remove_name in candidate_title
                                or candidate_title in remove_name
                            )
                            for remove_name in normalized_remove_names
                        ):
                            replacement_slot = slot
                            break

                    if replacement_slot is not None:
                        break

            # --------------------------------------------------------
            # candidates에서 못 찾으면 최종 itinerary에서 찾는다.
            # --------------------------------------------------------
            if replacement_slot is None:
                stops_by_key = _itinerary_stops_by_key(
                    state.itinerary
                )

                for (day_no, sequence), stop in stops_by_key.items():
                    stop_title = _normalize_title(
                        str(stop.get("title") or "")
                    )

                    if any(
                        remove_name
                        and (
                            remove_name in stop_title
                            or stop_title in remove_name
                        )
                        for remove_name in normalized_remove_names
                    ):
                        replacement_slot = next(
                            (
                                slot
                                for slot in updated_slots
                                if slot.day == day_no
                                and slot.sequence == sequence
                            ),
                            None,
                        )

                        if replacement_slot is not None:
                            break

            # --------------------------------------------------------
            # 교체 대상이 없으면 추가 방식으로 fallback하지 않는다.
            #
            # "A 말고 B"라고 했는데 A를 못 찾았는데
            # B를 새로 추가해버리면 잘못된 수정이 되기 때문.
            # --------------------------------------------------------
            if replacement_slot is None:
                print(
                    "[revise] 추천 후보 교체 실패:",
                    f"remove_places={list(remove_places)}",
                    f"recommendation={title}",
                )

                return ChatUpdateResult(
                    mode="no_change",
                    state=state,
                    message=(
                        f"교체할 장소 "
                        f"'{remove_places[0]}'을 "
                        "기존 일정에서 찾지 못했어요."
                    ),
                )

            # --------------------------------------------------------
            # 교체 대상 슬롯의 role을 유지한다.
            #
            # 예:
            # 돌낭예술원(visit) -> 제주이호랜드(visit)
            # 제주미담(food) -> 다른 식당(food)
            # --------------------------------------------------------
            role = replacement_slot.role

            # 기존 slot의 구조를 그대로 유지하고 candidate만 교체
            replacement_slot.candidates = [
                SlotCandidate(
                    content_id=int(content_id),
                    title=title,
                    final_score=1.0,
                    similarity_score=1.0,
                    place={
                        "content_id": recommendation.get(
                            "content_id"
                        ),
                        "title": recommendation.get(
                            "title"
                        ),
                        "overview": recommendation.get(
                            "summary"
                        ),
                        "address": recommendation.get(
                            "address"
                        ),
                        "image_url": recommendation.get(
                            "thumbnail"
                        ),
                        "latitude": recommendation.get(
                            "latitude"
                        ),
                        "longitude": recommendation.get(
                            "longitude"
                        ),
                    },
                    forced=True,
                )
            ]

            changed_keys = {
                (
                    replacement_slot.day,
                    replacement_slot.sequence,
                )
            }

            changed_slot_payloads = [
                replacement_slot.to_dict()
            ]

            print(
                "[revise] 추천 후보 교체:",
                f"day={replacement_slot.day}",
                f"sequence={replacement_slot.sequence}",
                f"role={replacement_slot.role}",
                f"remove={list(remove_places)}",
                f"replace_with={title}",
            )

        # ============================================================
        # 2) 추가 모드
        # ============================================================
        else:
            candidate = SlotCandidate(
                content_id=int(content_id),
                title=title,
                final_score=1.0,
                similarity_score=1.0,
                place={
                    "content_id": recommendation.get(
                        "content_id"
                    ),
                    "title": recommendation.get(
                        "title"
                    ),
                    "overview": recommendation.get(
                        "summary"
                    ),
                    "address": recommendation.get(
                        "address"
                    ),
                    "image_url": recommendation.get(
                        "thumbnail"
                    ),
                    "latitude": recommendation.get(
                        "latitude"
                    ),
                    "longitude": recommendation.get(
                        "longitude"
                    ),
                },
                forced=True,
            )

            # --------------------------------------------------------
            # 2-a) 위치 지정 삽입 시도
            #
            # "A 다음에/앞에 B 추가해줘" 또는 "아침/점심/오후/저녁에
            # B 추가해줘" 처럼 위치 기준이 주어졌다면, 그 기준을 실제
            # 일정에서 찾아 정확한 위치에 끼워넣는다. 순서 재배열은
            # LLM이 아니라 코드가 결정한다.
            # --------------------------------------------------------
            insert_index: int | None = None
            day_no = target_day

            anchor_name = insert_after or insert_before
            if anchor_name:
                anchor_key = _find_anchor_stop_key(
                    state.itinerary, anchor_name, target_day
                )
                if anchor_key is not None:
                    anchor_day, anchor_sequence = anchor_key
                    day_no = anchor_day
                    anchor_stops = sorted(
                        (
                            stop
                            for (day, _sequence), stop in _itinerary_stops_by_key(
                                state.itinerary
                            ).items()
                            if day == anchor_day
                        ),
                        key=lambda stop: stop.get("sequence", 0),
                    )
                    anchor_index = next(
                        (
                            index
                            for index, stop in enumerate(anchor_stops)
                            if stop.get("sequence") == anchor_sequence
                        ),
                        None,
                    )
                    if anchor_index is not None:
                        insert_index = anchor_index + (1 if insert_after else 0)
                        print(
                            "[revise] 위치 지정 삽입(장소 기준):",
                            f"anchor={anchor_name}",
                            f"anchor_key={anchor_key}",
                            f"insert_after={bool(insert_after)}",
                            f"insert_index={insert_index}",
                        )
                else:
                    print(
                        "[revise] 위치 기준 장소를 찾지 못함 -> "
                        f"기본 위치(맨 뒤)로 추가: anchor={anchor_name}",
                    )

            if insert_index is None and time_period:
                day_no = day_no or 1
                day_stops_sorted = sorted(
                    (
                        stop
                        for (day, _seq), stop in _itinerary_stops_by_key(
                            state.itinerary
                        ).items()
                        if day == day_no
                    ),
                    key=lambda stop: stop.get("sequence", 0),
                )
                if day_stops_sorted:
                    insert_index = _resolve_time_period_index(
                        day_stops_sorted, time_period
                    )
                    print(
                        "[revise] 위치 지정 삽입(시간대 기준):",
                        f"day={day_no}",
                        f"time_period={time_period}",
                        f"insert_index={insert_index}",
                    )

            if insert_index is not None:
                day_no = day_no or 1
                (
                    updated_slots,
                    changed_keys,
                    changed_slot_payloads,
                ) = _rebuild_day_slots_with_insertion(
                    state=state,
                    updated_slots=updated_slots,
                    day_no=day_no,
                    insert_index=insert_index,
                    new_candidate=candidate,
                    new_role=role,
                )

                position_locked_day = day_no

                print(
                    "[revise] 위치 지정 삽입 완료:",
                    f"day={day_no}",
                    f"changed_keys={sorted(changed_keys)}",
                )

            else:
                # ------------------------------------------------
                # 2-b) 위치 기준이 없거나 못 찾음 -> 기존 방식(맨 뒤 추가)
                # ------------------------------------------------
                day_no = day_no or 1

                target_day_slots = [
                    slot
                    for slot in updated_slots
                    if slot.day == day_no
                ]

                if not target_day_slots:
                    print(
                        f"[revise] 추천 후보 직접 삽입 실패: day={day_no}"
                    )

                    return ChatUpdateResult(
                        mode="no_change",
                        state=state,
                        message=(
                            f"{day_no}일차 슬롯을 "
                            "찾지 못했어요."
                        ),
                    )

                next_sequence = (
                    max(
                        (
                            slot.sequence
                            for slot in target_day_slots
                        ),
                        default=0,
                    )
                    + 1
                )

                new_slot = ItinerarySlot(
                    day=day_no,
                    sequence=next_sequence,
                    role=role,
                    target_collections=tuple(
                        SLOT_TARGET_COLLECTIONS.get(
                            role,
                            (),
                        )
                    ),
                    itinerary_roles=tuple(
                        SLOT_ITINERARY_ROLES.get(
                            role,
                            (),
                        )
                    ),
                    stay_minutes=_DEFAULT_STAY_MINUTES_BY_ROLE.get(
                        role,
                        90,
                    ),
                    location_hint=None,
                    query="chat_recommendation",
                    candidates=[candidate],
                )

                updated_slots.append(new_slot)

                changed_keys = {
                    (day_no, next_sequence),
                }

                changed_slot_payloads = [
                    new_slot.to_dict()
                ]

                print(
                    "[revise] 추천 후보 직접 삽입:",
                    f"day={day_no}",
                    f"sequence={next_sequence}",
                    f"role={role}",
                    f"title={title}",
                )

        # ============================================================
        # 3) used_content_ids 재계산
        # ============================================================
        used_content_ids = {
            candidate.content_id
            for slot in updated_slots
            for candidate in slot.candidates
        }

        # ============================================================
        # 4) 변경된 슬롯만 LLM에 전달
        # ============================================================
        itinerary = self._container.llm_service.revise_itinerary(
            new_condition,
            state.itinerary,
            changed_slot_payloads,
        )

        # LLM이 변경 범위 밖의 일정을 건드리지 못하도록 복원
        itinerary = _enforce_revision_scope(
            state.itinerary,
            itinerary,
            changed_keys,
        )

        # ============================================================
        # 5) 새로운 상태 생성
        # ============================================================
        new_state = ItineraryState(
            condition=new_condition,
            slots=updated_slots,
            itinerary=itinerary,
            used_content_ids=used_content_ids,
            recommendations=state.recommendations,
        )

        # ============================================================
        # 6) 응답
        # ============================================================
        if remove_places:
            message = (
                f"'{remove_places[0]}' 대신 "
                f"'{title}'로 변경했어요. 🍊"
            )
        else:
            message = (
                f"추천해드린 '{title}'을 "
                f"{target_day or 1}일차 일정에 "
                "추가했어요. 🍊"
            )

        return ChatUpdateResult(
            mode="edit",
            state=new_state,
            message=message,
            locked_days=(
                (position_locked_day,)
                if position_locked_day is not None
                else ()
            ),
        )

    def _force_include_must_visit_places(
        self,
        condition: TravelCondition,
        slots: list[ItinerarySlot],
        used_content_ids: set[int],
        *,
        target_day: int | None = None,
    ) -> list[ItinerarySlot]:

        if not condition.must_visit_places:
            return []

        # 날짜가 지정되지 않은 경우:
        # 기존처럼 전체 일정에서 이미 포함된 장소를 확인한다.
        #
        # 날짜가 지정된 경우:
        # "그 날짜에 이미 있는지"만 확인한다.
        def is_place_in_day(place_name: str, day_no: int | None) -> bool:
            normalized_name = _normalize_title(place_name)

            for slot in slots:
                if day_no is not None and slot.day != day_no:
                    continue

                for candidate in slot.candidates:
                    candidate_title = _normalize_title(candidate.title)

                    if (
                        normalized_name
                        and (
                            normalized_name in candidate_title
                            or candidate_title in normalized_name
                        )
                    ):
                        return True

            return False

        # role별 슬롯 분리
        slots_by_role: dict[str, list[ItinerarySlot]] = {}

        for slot in slots:
            slots_by_role.setdefault(slot.role, []).append(slot)

        touched_slots: list[ItinerarySlot] = []

        for place_name in condition.must_visit_places:
            normalized_name = _normalize_title(place_name)

            if not normalized_name:
                continue

            # ------------------------------------------------------------
            # target_day가 지정되어 있으면:
            # 반드시 그 날짜에 있어야 한다.
            #
            # 다른 날짜에 이미 있어도 무조건 skip하지 않는다.
            # ------------------------------------------------------------
            if is_place_in_day(place_name, target_day):
                continue

            response = self._container.retrieval_service.search_places(
                place_name,
                filters=PlaceSearchFilters(
                    region_pairs=get_region_districts(condition.region),
                ),
                top_k=3,
            )

            if not response.places:
                continue

            match = _best_name_match(
                response.places,
                place_name,
            )
            if match is None:
                continue

            role = _infer_role_from_tags(match.tags)

            # ------------------------------------------------------------
            # target_day가 지정된 경우:
            # 해당 날짜 슬롯만 대상으로 한다.
            # ------------------------------------------------------------
            if target_day is not None:
                role_slots = [
                    slot
                    for slot in slots
                    if slot.day == target_day
                    and slot.role == role
                ]

                # 같은 role이 없으면 visit 슬롯으로 fallback
                if not role_slots:
                    role_slots = [
                        slot
                        for slot in slots
                        if slot.day == target_day
                        and slot.role == "visit"
                    ]

                # 그래도 없으면 해당 날짜의 아무 슬롯
                if not role_slots:
                    role_slots = [
                        slot
                        for slot in slots
                        if slot.day == target_day
                    ]

            else:
                # 기존 초기 일정 생성 방식
                role_slots = (
                    slots_by_role.get(role)
                    or slots_by_role.get("visit")
                    or slots
                )

            if not role_slots:
                continue

            target_slot = min(
                role_slots,
                key=lambda slot: (
                    any(
                        candidate.forced
                        for candidate in slot.candidates
                    ),
                    len(slot.candidates),
                ),
            )

            # ------------------------------------------------------------
            # 다른 날짜에 같은 장소가 있다면 제거한다.
            # target_day가 명시된 "이날로 넣어줘" 요청에서
            # 동일 장소가 여러 날 중복되는 것을 방지한다.
            # ------------------------------------------------------------
            if target_day is not None:
                for slot in slots:
                    if slot.day == target_day:
                        continue

                    slot.candidates[:] = [
                        candidate
                        for candidate in slot.candidates
                        if _normalize_title(candidate.title)
                        != normalized_name
                    ]

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


def _parse_position_delete_request(user_text: str) -> tuple[int, int] | None:
    if not _DELETE_REQUEST_RE.search(user_text):
        return None

    day_match = _DAY_POSITION_RE.search(user_text)
    sequence_match = _SEQUENCE_POSITION_RE.search(user_text)
    if not day_match or not sequence_match:
        return None

    sequence = (
        int(sequence_match.group(1))
        if sequence_match.group(1)
        else _KOREAN_ORDINALS[sequence_match.group("word")]
    )
    return int(day_match.group(1)), sequence


def _remove_schedule_entries(
    state: ItineraryState,
    *,
    titles: Sequence[str] = (),
    position: tuple[int, int] | None = None,
) -> tuple[list[ItinerarySlot], dict[str, Any], set[int], tuple[str, ...]]:
    normalized_titles = {_normalize_title(title) for title in titles}
    itinerary = deepcopy(state.itinerary)
    removed_keys: set[tuple[int, int]] = set()
    removed_titles: list[str] = []

    for day in itinerary.get("days", []):
        day_number = int(day.get("day") or 0)
        retained_stops = []
        for stop in day.get("stops", []):
            key = (day_number, int(stop.get("sequence") or 0))
            title = str(stop.get("title") or "")
            should_remove = key == position or _normalize_title(title) in normalized_titles
            if should_remove:
                removed_keys.add(key)
                if title:
                    removed_titles.append(title)
            else:
                retained_stops.append(stop)
        day["stops"] = retained_stops

    slots_by_key = {(slot.day, slot.sequence): slot for slot in state.slots}
    slots: list[ItinerarySlot] = []
    used_slot_keys: set[tuple[int, int]] = set()

    for day in itinerary.get("days", []):
        day_number = int(day.get("day") or 0)
        renumbered_stops = []
        for sequence, stop in enumerate(day.get("stops", []), start=1):
            old_key = (day_number, int(stop.get("sequence") or 0))
            updated_stop = deepcopy(stop)
            updated_stop["sequence"] = sequence
            renumbered_stops.append(updated_stop)

            slot = slots_by_key.get(old_key)
            if slot is not None:
                updated_slot = deepcopy(slot)
                updated_slot.sequence = sequence
                slots.append(updated_slot)
                used_slot_keys.add(old_key)
        day["stops"] = renumbered_stops

    for key, slot in slots_by_key.items():
        if key not in removed_keys and key not in used_slot_keys:
            slots.append(deepcopy(slot))

    slots.sort(key=lambda slot: (slot.day, slot.sequence))
    used_content_ids = {
        candidate.content_id
        for slot in slots
        for candidate in slot.candidates
    }
    return slots, itinerary, used_content_ids, tuple(dict.fromkeys(removed_titles))

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

def _find_recommended_place(
    recommendations: list[dict[str, Any]],
    place_name: str,
) -> dict[str, Any] | None:
    normalized_name = _normalize_title(place_name)

    if not normalized_name:
        return None

    for recommendation in recommendations:
        title = _normalize_title(
            str(recommendation.get("title") or "")
        )

        if (
            normalized_name == title
            or normalized_name in title
            or title in normalized_name
        ):
            return recommendation

    return None


# ------------------------------------------------------------------
# 자유채팅 편집 범위 좁히기 / 강제 적용 헬퍼
# ------------------------------------------------------------------


def _itinerary_stops_by_key(itinerary: dict[str, Any]) -> dict[tuple[int, int], dict[str, Any]]:
    stops_by_key: dict[tuple[int, int], dict[str, Any]] = {}
    for day in itinerary.get("days", []):
        day_no = day.get("day")
        for stop in day.get("stops", []):
            sequence = stop.get("sequence")
            if day_no is None or sequence is None:
                continue
            stops_by_key[(day_no, sequence)] = stop
    return stops_by_key


def _scope_affected_keys(
    state: ItineraryState, delta: ConditionDelta
) -> set[tuple[int, int]] | None:
    """가능하면 편집 대상을 특정 (day, sequence)로 좁힌다.

    반환값이 ``None``이면 "좁힐 근거가 없다"는 뜻이며, 이 경우 호출부는
    기존처럼 role 전체(모든 day)를 대상으로 삼는다. 좁힐 수 있는 근거는
    두 가지뿐이다:

    1. 사용자가 실제 일정에 있는 장소 이름을 직접 언급함
       (delta.add_excluded_places / add_must_visit_places 중 하나가
       현재 stop의 title과 일치)
    2. 사용자가 특정 일차를 명시함 (delta.target_day)

    두 근거 모두 없으면 "이 스타일 전체를 바꿔줘" 같은 진짜 폭넓은 요청일
    가능성이 높으므로 좁히지 않는다.
    """

    stops_by_key = _itinerary_stops_by_key(state.itinerary)
    if not stops_by_key:
        return None

    named_places = [
        place
        for place in (
            *delta.add_excluded_places,
            *delta.add_must_visit_places,
            *delta.remove_must_visit_places,
        )
        if place and place.strip()
    ]

    matched_keys: set[tuple[int, int]] = set()
    if named_places:
        normalized_names = [_normalize_title(name) for name in named_places]
        for key, stop in stops_by_key.items():
            title = _normalize_title(str(stop.get("title") or ""))
            if not title:
                continue
            for name in normalized_names:
                if name and (name in title or title in name):
                    matched_keys.add(key)
                    break

    if matched_keys:
        if delta.target_day is not None:
            matched_keys = {key for key in matched_keys if key[0] == delta.target_day}
        return matched_keys

    if delta.target_day is not None:
        return {key for key in stops_by_key if key[0] == delta.target_day}

    return None


def _enforce_revision_scope(
    original_itinerary: dict[str, Any],
    revised_itinerary: dict[str, Any],
    changed_keys: set[tuple[int, int]],
) -> dict[str, Any]:
    """LLM이 changed_keys 밖의 stop을 바꿨더라도 원본으로 강제 복원한다.

    프롬프트로 "이 부분만 바꿔라"라고 아무리 강하게 지시해도 LLM이 완벽히
    지키리라는 보장은 없다. 그래서 changed_keys에 없는 day는 통째로,
    changed_keys에 없는 stop은 개별적으로 원본 그대로 되돌려서, 사용자가
    요청한 부분 외에는 절대 바뀌지 않는다는 것을 코드 레벨에서 보장한다.
    """

    original_days = {
        day.get("day"): day for day in original_itinerary.get("days", [])
    }
    changed_days = {day_no for day_no, _ in changed_keys}

    result_days: list[dict[str, Any]] = []
    seen_day_numbers: set[int] = set()

    for day in revised_itinerary.get("days", []):
        day_no = day.get("day")
        seen_day_numbers.add(day_no)

        if day_no not in changed_days:
            # 이 day는 요청과 전혀 관련이 없다 -> 원본 그대로 복원
            if day_no in original_days:
                result_days.append(copy.deepcopy(original_days[day_no]))
            else:
                result_days.append(day)
            continue

        # 이 day는 일부 stop이 바뀌어야 하는 day. changed_keys에 없는
        # sequence는 stop 단위로 원본을 복원한다.
        original_stops_by_seq = {
            stop.get("sequence"): stop
            for stop in original_days.get(day_no, {}).get("stops", [])
        }
        merged_stops = []
        for stop in day.get("stops", []):
            sequence = stop.get("sequence")
            key = (day_no, sequence)
            if key not in changed_keys and sequence in original_stops_by_seq:
                merged_stops.append(copy.deepcopy(original_stops_by_seq[sequence]))
            else:
                merged_stops.append(stop)

        merged_day = dict(day)
        merged_day["stops"] = merged_stops
        result_days.append(merged_day)

    # 혹시 LLM이 통째로 빠뜨린 day가 있으면 원본에서 그대로 채워 넣는다
    # (day 자체가 사라지는 것도 "요청하지 않은 변경"이기 때문).
    for day_no, day in original_days.items():
        if day_no not in seen_day_numbers:
            result_days.append(copy.deepcopy(day))

    result_days.sort(key=lambda d: (d.get("day") is None, d.get("day", 0)))

    merged = dict(revised_itinerary)
    merged["days"] = result_days
    return merged


def _candidate_to_recommendation(candidate: SlotCandidate) -> dict[str, Any]:
    place = candidate.place or {}
    overview = str(place.get("overview") or "").strip()
    summary = overview[:120] + ("…" if len(overview) > 120 else "") if overview else ""

    return {
        "content_id": candidate.content_id,
        "title": candidate.title,
        "summary": summary,
        "address": place.get("address") or place.get("road_address") or "",
        "thumbnail": (
            place.get("image_url")
            or place.get("thumbnail_url")
            or place.get("thumbnail")
            or ""
        ),
        "latitude": place.get("latitude"),
        "longitude": place.get("longitude"),
    }


_ROLE_LABEL_KO: dict[str, str] = {
    "visit": "관광지",
    "activity": "액티비티",
    "food": "맛집/카페",
    "shopping": "쇼핑",
}


def _build_recommend_message(delta: ConditionDelta, recommendations: list[dict[str, Any]]) -> str:
    affected_roles = list(dict.fromkeys(infer_affected_slots(delta)))
    role = affected_roles[0] if affected_roles else "food"
    label = _ROLE_LABEL_KO.get(role, "장소")

    if not recommendations:
        return f"조건에 맞는 {label} 후보를 찾지 못했어요. 다른 조건으로 다시 물어봐주세요."

    return (
        f"{label} 후보를 {len(recommendations)}곳 찾아봤어요. "
        "마음에 드는 곳이 있으면 "
        "'하도해변을 2일차에 추가해줘'처럼 말씀해주시면 "
        "일정에 반영할게요."
    )


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


def _best_name_match(
    places: Sequence[RetrievedPlace],
    name: str,
) -> RetrievedPlace | None:
    normalized_name = _normalize_title(name)
    for place in places:
        normalized_title = _normalize_title(place.title)
        if normalized_name in normalized_title or normalized_title in normalized_name:
            return place
    return None


def _find_anchor_stop_key(
    itinerary: dict[str, Any],
    anchor_name: str,
    target_day: int | None,
) -> tuple[int, int] | None:
    """"A 다음/앞에" 요청에서 기준이 되는 A를 실제 일정에서 찾는다.

    target_day가 주어지면 해당 day에서만 찾는다. 못 찾으면 target_day
    제한을 풀고 다시 시도한다 (사용자가 A만 언급하고 day를 착각했을 수도
    있으므로, 완전히 실패로 처리하기 전에 한 번 더 시도).
    """

    normalized_anchor = _normalize_title(anchor_name)
    if not normalized_anchor:
        return None

    stops_by_key = _itinerary_stops_by_key(itinerary)

    def _search(day_filter: int | None) -> tuple[int, int] | None:
        for (day_no, sequence), stop in stops_by_key.items():
            if day_filter is not None and day_no != day_filter:
                continue
            stop_title = _normalize_title(str(stop.get("title") or ""))
            if not stop_title:
                continue
            if normalized_anchor in stop_title or stop_title in normalized_anchor:
                return (day_no, sequence)
        return None

    result = _search(target_day)
    if result is not None:
        return result
    if target_day is not None:
        return _search(None)
    return None


def _resolve_time_period_index(
    day_stops: list[dict[str, Any]],
    time_period: str,
) -> int:
    """시간대(아침/점심/오후/저녁) 요청을 해당 day의 삽입 인덱스(0-based)로
    변환한다. day_stops는 sequence 오름차순으로 정렬되어 있어야 한다.

    규칙 (문서의 "배치 규칙"을 그대로 코드화):
    - morning : 그 날 첫 스톱 앞
    - lunch   : 그 날 첫 food 슬롯(보통 점심) 앞
    - afternoon : 첫 food 슬롯(점심) 바로 뒤
    - evening : 마지막 food 슬롯(보통 저녁) 앞, food가 없으면 맨 뒤
    """

    if not day_stops:
        return 0

    food_indexes = [
        index
        for index, stop in enumerate(day_stops)
        if stop.get("role") == "food"
    ]

    if time_period == "morning":
        return 0

    if time_period == "lunch":
        return food_indexes[0] if food_indexes else len(day_stops) // 2

    if time_period == "afternoon":
        return food_indexes[0] + 1 if food_indexes else len(day_stops) // 2 + 1

    if time_period == "evening":
        return food_indexes[-1] if food_indexes else len(day_stops)

    return len(day_stops)


def _rebuild_day_slots_with_insertion(
    *,
    state: ItineraryState,
    updated_slots: list[ItinerarySlot],
    day_no: int,
    insert_index: int,
    new_candidate: SlotCandidate,
    new_role: str,
) -> tuple[list[ItinerarySlot], set[tuple[int, int]], list[dict[str, Any]]]:
    """지정된 day 안에서 insert_index 위치에 new_candidate를 끼워넣고,
    그 day 전체의 sequence를 1부터 다시 매긴다.

    "A 다음에 B" 같은 순서 요청은 LLM에게 판단을 맡기면 안 되므로, 이
    함수가 최종 순서를 코드 레벨에서 확정한다. 기존 stop들은 각각
    forced=True인 단일 후보로 다시 만들어서 changed_slots로 넘기므로,
    LLM(revise_itinerary)은 지정된 content_id 순서를 그대로 유지한 채
    start_time/end_time/notes만 자연스럽게 채운다.
    """

    stops_by_key = _itinerary_stops_by_key(state.itinerary)
    day_stops = sorted(
        (stop for (day, _seq), stop in stops_by_key.items() if day == day_no),
        key=lambda stop: stop.get("sequence", 0),
    )

    # 기존 slot의 candidate.place에는 image_url/thumbnail_url 등 썸네일
    # 정보가 들어있다. 아래에서 day 전체를 스켈레톤으로 재구성하면서 이
    # place 정보를 그대로 들고 있지 않으면, 이 day의 모든 항목(새로
    # 추가되는 장소가 아닌 기존 장소들)이 썸네일을 잃어버리게 된다.
    # content_id 기준으로 기존 place 정보를 미리 모아둔다.
    existing_place_by_content_id: dict[int, dict[str, Any]] = {}
    for existing_slot in state.slots:
        if existing_slot.day != day_no:
            continue
        for existing_candidate in existing_slot.candidates:
            if existing_candidate.content_id is not None:
                existing_place_by_content_id[existing_candidate.content_id] = (
                    existing_candidate.place or {}
                )

    # 기존 stop들을 (content_id, title, role, 좌표) 스켈레톤으로 변환
    skeletons: list[dict[str, Any]] = []
    for stop in day_stops:
        stop_content_id = stop.get("content_id")
        existing_place = (
            existing_place_by_content_id.get(int(stop_content_id))
            if stop_content_id is not None
            else None
        ) or {}
        skeletons.append(
            {
                "content_id": stop_content_id,
                "title": stop.get("title"),
                "role": stop.get("role") or "visit",
                "latitude": stop.get("latitude"),
                "longitude": stop.get("longitude"),
                "thumbnail": (
                    stop.get("image_url")
                    or stop.get("thumbnail_url")
                    or stop.get("thumbnail")
                    or existing_place.get("image_url")
                    or existing_place.get("thumbnail_url")
                    or existing_place.get("thumbnail")
                ),
            }
        )

    new_place = new_candidate.place or {}
    new_skeleton = {
        "content_id": new_candidate.content_id,
        "title": new_candidate.title,
        "role": new_role,
        "latitude": new_place.get("latitude"),
        "longitude": new_place.get("longitude"),
        "_new": True,
    }

    insert_at = max(0, min(insert_index, len(skeletons)))
    skeletons.insert(insert_at, new_skeleton)

    remaining_slots = [slot for slot in updated_slots if slot.day != day_no]

    new_day_slots: list[ItinerarySlot] = []
    changed_keys: set[tuple[int, int]] = set()
    changed_slot_payloads: list[dict[str, Any]] = []

    for sequence, skeleton in enumerate(skeletons, start=1):
        role = skeleton["role"]

        if skeleton.get("_new"):
            candidate = new_candidate
        else:
            candidate = SlotCandidate(
                content_id=int(skeleton["content_id"]),
                title=skeleton.get("title") or "",
                final_score=1.0,
                similarity_score=1.0,
                place={
                    "content_id": skeleton.get("content_id"),
                    "title": skeleton.get("title"),
                    "latitude": skeleton.get("latitude"),
                    "longitude": skeleton.get("longitude"),
                    # 기존에 갖고 있던 썸네일 정보를 유지한다.
                    # (이게 없으면 day 재정렬 시 기존 장소들의
                    # 이미지가 전부 사라져 버린다.)
                    "image_url": skeleton.get("thumbnail") or "",
                },
                forced=True,
            )

        slot = ItinerarySlot(
            day=day_no,
            sequence=sequence,
            role=role,
            target_collections=tuple(SLOT_TARGET_COLLECTIONS.get(role, ())),
            itinerary_roles=tuple(SLOT_ITINERARY_ROLES.get(role, ())),
            stay_minutes=_DEFAULT_STAY_MINUTES_BY_ROLE.get(role, 90),
            location_hint=None,
            query="chat_recommendation_insert",
            candidates=[candidate],
        )

        new_day_slots.append(slot)
        changed_keys.add((day_no, sequence))
        changed_slot_payloads.append(slot.to_dict())

    remaining_slots.extend(new_day_slots)

    return remaining_slots, changed_keys, changed_slot_payloads


def _day_stop_coords(
    state: "ItineraryState", day_no: int | None
) -> list[tuple[int, float, float]]:
    """day_no의 stop들을 (sequence, latitude, longitude)로, sequence
    오름차순 정렬해서 반환한다. day_no가 None이면 일정 전체 stop을
    (day, sequence)를 무시하고 좌표만 모은다 (호출부에서 day_no가 없는
    경우는 "day 평균" 용도로만 쓰고, 순서 기반 로직에는 안 쓴다).

    좌표가 없는 stop은 건너뛴다.
    """

    coords: list[tuple[int, float, float]] = []

    for day in state.itinerary.get("days", []):
        if day_no is not None and day.get("day") != day_no:
            continue
        for stop in day.get("stops", []):
            lat = stop.get("latitude")
            lng = stop.get("longitude")
            sequence = stop.get("sequence")
            if lat is None or lng is None or sequence is None:
                continue
            coords.append((int(sequence), float(lat), float(lng)))

    coords.sort(key=lambda item: item[0])
    return coords


def _find_stop_key_by_name(
    state: "ItineraryState", name: str, day_no: int | None = None
) -> tuple[int, int] | None:
    """이름으로 기존 일정 안의 stop을 찾아 (day, sequence)를 반환한다.

    "헬로효주 대신 제주당으로 바꿔줘"처럼 교체 대상(헬로효주)은 이미
    일정에 있는 stop이므로, 그 stop의 정확한 위치를 알아야 "그 자리
    앞뒤 장소 사이"로 후보를 좁힐 수 있다. 못 찾으면 None.
    """

    normalized_name = _normalize_title(name)
    if not normalized_name:
        return None

    for day in state.itinerary.get("days", []):
        if day_no is not None and day.get("day") != day_no:
            continue
        for stop in day.get("stops", []):
            title = _normalize_title(str(stop.get("title") or ""))
            if not title:
                continue
            if normalized_name in title or title in normalized_name:
                sequence = stop.get("sequence")
                day_value = day.get("day")
                if sequence is None or day_value is None:
                    continue
                return (int(day_value), int(sequence))

    return None


def _neighbor_coords_for_sequence(
    day_coords: list[tuple[int, float, float]], sequence: int
) -> tuple[tuple[float, float] | None, tuple[float, float] | None]:
    """정렬된 day_coords에서 sequence 바로 앞/뒤 stop의 좌표를 찾는다.

    sequence가 그 day의 첫 slot이면 prev는 None, 마지막 slot이면
    next는 None (출발지/도착지 취급은 호출부에서 필요하면 처리).
    """

    prev_coord: tuple[float, float] | None = None
    next_coord: tuple[float, float] | None = None

    for seq, lat, lng in day_coords:
        if seq < sequence:
            prev_coord = (lat, lng)
        elif seq > sequence and next_coord is None:
            next_coord = (lat, lng)

    return prev_coord, next_coord


def _detour_km(
    prev_coord: tuple[float, float] | None,
    next_coord: tuple[float, float] | None,
    candidate_coord: tuple[float, float],
) -> float | None:
    """prev -> candidate -> next로 갔을 때, prev -> next 직행 대비 얼마나
    더 돌아가는지(km)를 계산한다.

    prev/next 중 하나가 없으면(맨 앞/맨 뒤에 넣는 경우) 있는 쪽까지의
    단순 거리로 근사한다. 둘 다 없으면 비교 기준이 없으므로 None.
    """

    d_prev_cand = (
        haversine_km(prev_coord[0], prev_coord[1], candidate_coord[0], candidate_coord[1])
        if prev_coord
        else None
    )
    d_cand_next = (
        haversine_km(candidate_coord[0], candidate_coord[1], next_coord[0], next_coord[1])
        if next_coord
        else None
    )

    if d_prev_cand is not None and d_cand_next is not None:
        d_prev_next = haversine_km(
            prev_coord[0], prev_coord[1], next_coord[0], next_coord[1]
        )
        baseline = d_prev_next if d_prev_next is not None else 0.0
        return d_prev_cand + d_cand_next - baseline

    if d_prev_cand is not None:
        return d_prev_cand

    if d_cand_next is not None:
        return d_cand_next

    return None


def _best_detour_km_in_day(
    day_coords: list[tuple[int, float, float]],
    candidate_coord: tuple[float, float],
) -> float | None:
    """day_coords의 모든 삽입 위치(맨 앞/사이/맨 뒤) 중, candidate를
    넣었을 때 가장 우회가 적은 값을 찾는다.

    사용자가 특정 슬롯을 지정하지 않고 "1일차 카페 추천해줘"라고 했을
    때 쓴다 - 어디에 넣을지는 아직 안 정했으니, "이 day 어딘가에 넣는다면
    가장 자연스러운 후보가 뭔가"를 판단하는 용도.
    """

    if not day_coords:
        return None

    points: list[tuple[float, float] | None] = (
        [None] + [(lat, lng) for _, lat, lng in day_coords] + [None]
    )

    best: float | None = None

    for i in range(len(points) - 1):
        cost = _detour_km(points[i], points[i + 1], candidate_coord)
        if cost is None:
            continue
        if best is None or cost < best:
            best = cost

    return best


def _anchor_location_hint(
    state: "ItineraryState", day_no: int | None, target_sequence: int | None
) -> dict[str, float] | None:
    """"근처" 검색의 기준점(위도/경도)을 만든다.

    target_sequence가 있으면(특정 슬롯을 바꾸는 경우) 그 슬롯의 바로
    앞/뒤 장소 좌표 평균을 기준점으로 쓴다. 이렇게 해야 예를 들어 1일차
    6개 장소 중 2번째를 바꾸는데, 6번째 장소 근처의 카페가 "가깝다"는
    이유로 걸러지지 않고 먼저 걸러지는 문제를 막을 수 있다.

    target_sequence가 없으면(day 전체에서 아무 위치에나 추가하는 경우)
    기존처럼 day 전체 stop 좌표 평균을 쓴다.

    좌표가 있는 stop이 하나도 없으면 None (호출부는 위치 필터 없이
    검색하게 된다).
    """

    if day_no is None:
        return None

    day_coords = _day_stop_coords(state, day_no)
    if not day_coords:
        return None

    if target_sequence is not None:
        prev_coord, next_coord = _neighbor_coords_for_sequence(
            day_coords, target_sequence
        )
        neighbor_points = [p for p in (prev_coord, next_coord) if p is not None]
        if neighbor_points:
            return {
                "latitude": sum(p[0] for p in neighbor_points) / len(neighbor_points),
                "longitude": sum(p[1] for p in neighbor_points) / len(neighbor_points),
            }

    return {
        "latitude": sum(lat for _, lat, _ in day_coords) / len(day_coords),
        "longitude": sum(lng for _, _, lng in day_coords) / len(day_coords),
    }


def _rerank_recommendations_by_route(
    recommendations: list[dict[str, Any]],
    *,
    state: "ItineraryState",
    day_no: int | None,
    target_sequence: int | None,
) -> list[dict[str, Any]]:
    """추천 후보를 "day 평균 위치와 가까운 순"이 아니라 "기존 동선에
    넣었을 때 우회가 가장 적은 순"으로 다시 정렬한다.

    - target_sequence가 있으면: 그 슬롯의 앞/뒤 장소 사이에 넣었을 때의
      우회 거리만 본다 (예: "2번째 카페 바꿔줘").
    - target_sequence가 없으면: 그 day의 모든 삽입 위치 중 가장 우회가
      적은 값을 본다 (예: "1일차 카페 추천해줘").

    day_no가 없거나, day에 좌표 있는 stop이 하나도 없으면(예: 새로
    만드는 날짜) 재정렬하지 않고 원래 순서를 그대로 둔다. 좌표가 없는
    추천 후보도 마찬가지로 순서를 그대로 두되, 좌표가 있는 후보들
    뒤로 보낸다 (우회 거리를 모르는 후보를 우선순위 있는 것처럼
    보여주지 않기 위해서).
    """

    if day_no is None:
        return recommendations

    day_coords = _day_stop_coords(state, day_no)
    if not day_coords:
        return recommendations

    scored: list[tuple[float, int, dict[str, Any]]] = []
    unscored: list[dict[str, Any]] = []

    for index, recommendation in enumerate(recommendations):
        lat = recommendation.get("latitude")
        lng = recommendation.get("longitude")
        if lat is None or lng is None:
            unscored.append(recommendation)
            continue

        candidate_coord = (float(lat), float(lng))

        if target_sequence is not None:
            prev_coord, next_coord = _neighbor_coords_for_sequence(
                day_coords, target_sequence
            )
            cost = _detour_km(prev_coord, next_coord, candidate_coord)
        else:
            cost = _best_detour_km_in_day(day_coords, candidate_coord)

        if cost is None:
            unscored.append(recommendation)
        else:
            scored.append((cost, index, recommendation))

    scored.sort(key=lambda item: (item[0], item[1]))
    return [recommendation for _, _, recommendation in scored] + unscored

def _location_hint_for_day(
    state: ItineraryState,
    day_no: int | None,
) -> dict[str, float] | None:
    coordinates = [
        (stop.get("latitude"), stop.get("longitude"))
        for day in state.itinerary.get("days", [])
        if day_no is None or day.get("day") == day_no
        for stop in day.get("stops", [])
        if stop.get("latitude") is not None and stop.get("longitude") is not None
    ]
    if not coordinates:
        return None

    return {
        "latitude": sum(float(latitude) for latitude, _ in coordinates) / len(coordinates),
        "longitude": sum(float(longitude) for _, longitude in coordinates) / len(coordinates),
    }


def _group_slots_by_day(slots: list[ItinerarySlot]) -> list[dict[str, Any]]:
    days: dict[int, list[dict[str, Any]]] = {}
    for slot in slots:
        days.setdefault(slot.day, []).append(slot.to_dict())
    return [
        {"day": day_no, "slots": sorted(day_slots, key=lambda item: item["sequence"])}
        for day_no, day_slots in sorted(days.items())
    ]


def _default_day_structure(condition: TravelCondition) -> list[dict[str, Any]]:
    roles = ("visit", "activity", "food", "visit", "food")
    return [
        {
            "day": day_no,
            "region": None,
            "slot_count": len(roles),
            "slots": [
                {
                    "sequence": sequence,
                    "role": role,
                    "target_collections": list(SLOT_TARGET_COLLECTIONS[role]),
                    "itinerary_roles": list(SLOT_ITINERARY_ROLES[role]),
                    "stay_minutes": _DEFAULT_STAY_MINUTES_BY_ROLE[role],
                    "location_hint": None,
                }
                for sequence, role in enumerate(roles, start=1)
            ],
        }
        for day_no in range(1, condition.duration_days + 1)
    ]


def _dynamic_day_structure(
    condition: TravelCondition,
    pool_by_role: dict[str, list[RetrievedPlace]],
    *,
    matches: Sequence[Any] | None = None,
    movement_patterns: dict[str, Any] | None = None,
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
            movement_patterns=movement_patterns,
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
    movement_patterns: dict[str, Any] | None = None,
) -> list[str]:
    if count <= 0:
        return []

    available_counts = {
        role: len(places)
        for role, places in pool_by_role.items()
        if places
    }
    if not available_counts:
        return ["visit"] * count

    priority_roles: list[str] = []
    if movement_patterns and movement_patterns.get("available"):
        for value in movement_patterns.get("most_common_daily_role_order", []):
            role = str(value).strip()
            if role in available_counts and role not in priority_roles:
                priority_roles.append(role)

    for preference in condition.preferred_visit_types:
        for role in _ROLE_PRIORITY_BY_PREFERENCE.get(
            preference.value,
            (),
        ):
            if role in available_counts and role not in priority_roles:
                priority_roles.append(role)

    for role in ("visit", "food", "activity", "shopping"):
        if role in available_counts and role not in priority_roles:
            priority_roles.append(role)

    roles: list[str] = []
    used_by_role: Counter[str] = Counter()
    while len(roles) < count:
        progressed = False
        for role in priority_roles:
            if len(roles) >= count:
                break
            if used_by_role[role] >= available_counts[role]:
                continue
            roles.append(role)
            used_by_role[role] += 1
            progressed = True
        if not progressed:
            break

    if len(roles) < count:
        fallback = roles or priority_roles
        index = 0
        while len(roles) < count and fallback:
            roles.append(fallback[index % len(fallback)])
            index += 1

    return roles[:count]
