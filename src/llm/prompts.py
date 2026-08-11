from __future__ import annotations

import json
from typing import Any

from ..models.travel_condition import LocalTransport, Pace, PartyType, VisitPreference

PARTY_TYPE_VALUES = [item.value for item in PartyType]
LOCAL_TRANSPORT_VALUES = [item.value for item in LocalTransport]
VISIT_PREFERENCE_VALUES = [item.value for item in VisitPreference]
PACE_VALUES = [item.value for item in Pace]

# ---------------------------------------------------s------------------------
# 1. Condition extraction (first turn: free text -> TravelCondition JSON)
# ---------------------------------------------------------------------------

CONDITION_EXTRACTION_SYSTEM_PROMPT = f"""당신은 제주 여행 일정 서비스의 조건 추출기입니다.
사용자의 문장에서 여행 조건을 추출하여 아래 스키마의 JSON 객체 하나만 출력하세요.
설명, 마크다운, 다른 텍스트는 절대 포함하지 마세요.

스키마:
{{
  "duration_days": 정수 (1~30),
  "party_type": {PARTY_TYPE_VALUES} 중 하나,
  "local_transport": {LOCAL_TRANSPORT_VALUES} 중 하나,
  "preferred_visit_types": {VISIT_PREFERENCE_VALUES} 중 1개 이상을 담은 배열,
  "companion_count": 정수 또는 null,
  "age_group": 문자열 또는 null,
  "pace": {PACE_VALUES} 중 하나 또는 null,
  "must_visit_places": 문자열 배열 (없으면 []),
  "excluded_places": 문자열 배열 (없으면 [])
}}

여행 스타일(travel_style) 매핑 규칙:
- "힐링형" -> ["nature", "leisure"]
- "액티비티" -> ["experience", "theme_park"]
- "맛집" -> ["food_cafe"]
- "트래킹" -> ["trail"]
여러 스타일이 언급되면 해당하는 값을 모두 포함하세요.

나이대(age_group) 추출 규칙:
- "20대" -> "20s"
- "30대" -> "30s"
- "40대" -> "40s"
- "50대" -> "50s"
- "60대" -> "60s"
- "70대" -> "70s"
- 사용자가 나이대를 명시하지 않았으면 null
- 반드시 사용자가 명시한 나이대를 그대로 기준으로 추출하세요.

정보가 불명확하면 합리적인 기본값을 사용하되(party_type 기본값 "non_family_group",
local_transport 기본값 "rental_car"), duration_days와 preferred_visit_types는
반드시 사용자의 문장에서 최대한 추론하세요."""


def build_condition_extraction_prompt(user_text: str) -> str:
    return user_text.strip()


# ---------------------------------------------------------------------------
# 2. RAG search-query generation
# ---------------------------------------------------------------------------

QUERY_GENERATION_SYSTEM_PROMPT = """당신은 제주 여행 장소 검색을 위한 검색어(Query) 생성기입니다.
주어진 여행 조건과 지금 채우려는 일정 슬롯 정보를 바탕으로, 벡터 검색(Chroma)에
사용할 자연스러운 한국어 검색어 하나를 생성하세요.

다음 JSON 객체 하나만 출력하세요: {"query": "..."}

규칙:
- 슬롯의 role(visit/activity/food/shopping)에 맞는 장소 종류만 검색되도록 검색어를 구성하세요.
  예: food -> 맛집/음식점, shopping -> 시장/쇼핑
- 동행자, 교통수단, 여행 스타일, (있다면) 사용자의 추가 요청을 검색어에 반영하세요.
- 검색어는 5~10 단어 내외의 간결한 구문으로 작성하세요. 문장으로 쓰지 마세요."""


def build_query_generation_prompt(
    condition_dict: dict[str, Any],
    *,
    slot_role: str,
    day: int,
    extra_request: str | None = None,
) -> str:
    payload = {
        "condition": condition_dict,
        "slot": {"role": slot_role, "day": day},
        "extra_request": extra_request,
    }
    return json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 2-b. RAG search-query generation (whole-trip, role-agnostic)
# ---------------------------------------------------------------------------

STYLE_QUERY_GENERATION_SYSTEM_PROMPT = """당신은 제주 여행 콘텐츠 검색을 위한 검색어(Query) 생성기입니다.
특정 슬롯(role)을 위한 것이 아니라, 여행 전체 후보 풀을 채우기 위한 검색어를 만듭니다.
주어진 여행 조건(스타일 preferred_visit_types, 꼭 가고 싶은 곳 must_visit_places 등)을
모두 반영해서, 관광지/맛집/카페/액티비티/쇼핑을 폭넓게 아우르는 벡터 검색용
한국어 검색어 하나를 생성하세요.

입력에는 condition 외에 reference_keywords가 함께 들어올 수 있습니다.
reference_keywords는 조건(기간/동행/교통수단)이 비슷한 다른 여행자들이 실제로
방문한 장소를 role(visit/activity/food/shopping)별로 정리한 참고 자료입니다.

다음 JSON 객체 하나만 출력하세요: {"query": "..."}

규칙:
- 특정 role(음식/쇼핑 등) 하나에 국한하지 말고, preferred_visit_types 전체를 반영하세요.
- must_visit_places가 있다면 검색어에 함께 녹여내세요 (예: "흑돼지").
- 동행자, 교통수단도 자연스럽게 반영할 수 있으면 반영하세요.
- reference_keywords가 있다면 검색 방향을 구체화하는 참고 자료로만 사용하세요
  (예: visit에 "성산일출봉"이 있으면 "성산일출봉과 비슷한 자연 관광지"처럼 검색어에
  녹여내되, 그 장소 이름 자체를 결과로 보장하려는 것이 아닙니다).
- condition(사용자 조건)과 reference_keywords가 서로 다른 방향을 가리키면 항상
  condition을 우선하세요. reference_keywords는 어디까지나 보조 신호입니다.
- 검색어는 5~12 단어 내외의 간결한 구문으로 작성하세요. 문장으로 쓰지 마세요."""


def build_style_query_generation_prompt(
    condition_dict: dict[str, Any],
    *,
    reference_keywords: dict[str, list[str]] | None = None,
) -> str:
    payload: dict[str, Any] = {"condition": condition_dict}
    if reference_keywords:
        payload["reference_keywords"] = reference_keywords
    return json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 3. Itinerary generation (first turn: candidates -> final schedule)
# ---------------------------------------------------------------------------

ITINERARY_GENERATION_SYSTEM_PROMPT = """당신은 제주 여행 일정을 완성하는 플래너입니다.
전달되는 입력은 세 가지입니다.

1. condition — 사용자 조건
2. days — Planner가 이미 결정한 슬롯 구조(하루에 몇 개의 슬롯을, 어떤 role로
   방문할지)와, 슬롯별 후보 장소(RAG 검색 결과)
3. movement_patterns — 동행/기간이 비슷한 여러 AIHub 여행에서 공통적으로
   나타난 "이동 패턴" 요약 (실제 관광지 이름은 포함되어 있지 않음)

다음 JSON 객체 하나만 출력하세요:
{
  "days": [
    {
      "day": 1,
      "title": "짧은 하루 제목",
      "stops": [
        {
          "sequence": 1,
          "role": "visit",
          "content_id": 12345,
          "title": "장소명",
          "start_time": "09:00",
          "end_time": "10:30",
          "notes": "이동/방문 관련 짧은 메모"
        }
      ]
    }
  ]
}

## 각 입력의 역할 (반드시 구분해서 사용)

- Planner(days의 슬롯 구조) — "몇 개를 방문할지"를 이미 결정했습니다.
  각 day의 슬롯 개수는 반드시 그대로 유지하세요. 줄이거나 늘리지 마세요.
- RAG(슬롯별 candidates) — "어디를 갈 수 있는지" 후보입니다.
  모든 관광지는 반드시 이 후보 안에서만 선택하세요. 후보에 없는 장소를
  새로 만들어내거나 추가해서는 안 됩니다.
- AIHub(movement_patterns) — "비슷한 사람들이 어떻게 이동했는지"에 대한
  참고자료입니다. most_common_daily_role_order, role_transitions 같은
  값을 참고해서 하루 동선의 순서·흐름을 자연스럽게 정하는 데에만 사용하세요.
  movement_patterns 안에는 실제 관광지 이름이 없으므로, 이 값으로 장소를
  선택하거나 특정 여행을 그대로 재현하려고 하지 마세요.

## 우선순위 (충돌 시 이 순서를 따르세요)

1. Planner가 결정한 슬롯 구조(day별 슬롯 개수)
2. RAG 후보 관광지(candidates)
3. AIHub의 공통 이동 패턴(movement_patterns) — 순서 배치 참고용

## 일정 생성 순서

1. Planner가 생성한 슬롯 구조를 그대로 유지합니다.
2. movement_patterns의 공통 순서/흐름을 참고합니다.
3. 각 슬롯의 candidates 중에서 가장 적합한 장소를 선택합니다.
4. 같은 날 안에서는 candidates의 location_hint를 참고해 이동 거리가
   최소화되도록 순서를 정합니다.
5. 식사는 식사 시간대에, 카페 등 휴식은 관광 후 자연스럽게 배치합니다.
6. 모든 슬롯을 반드시 채웁니다. (candidates가 정말 비어 있는 슬롯만 예외)

## 그 외 규칙

- 각 슬롯의 candidates에 있는 content_id만 사용하세요.
- 같은 content_id를 두 번 이상 사용하지 마세요.
- candidates 중 "forced": true 로 표시된 장소는 사용자가 반드시 포함해달라고
  요청한 장소입니다. 해당 슬롯의 stop으로 반드시 선택하세요.
- 사용자의 교통수단(local_transport)을 고려하여 현실적인 이동 시간을 두고
  시간을 배치하세요.
- 각 장소 후보의 opening_hours/closed_days를 참고하여 방문 가능한 시간대에
  배치하세요.

## 최종 목표

목표는 AIHub의 특정 여행을 재현하거나 RAG 후보를 단순 나열하는 것이 아니라,
Planner의 슬롯 구조를 유지하고 RAG 후보만 사용하면서, AIHub의 공통 이동
패턴을 참고하여 사용자 조건에 맞는 새로운 여행 일정을 만드는 것입니다.

### 매우 중요한 규칙 ###
- 입력으로 전달된 days 배열의 개수와 동일한 개수의 days를 반드시 반환하세요.
- day를 생략하지 마세요.
- 입력이 2일이면 day1~day2를 모두 반환하세요.
- 입력이 3일이면 day1~day3을 모두 반환하세요.
- 입력이 4일이면 day1~day4를 모두 반환하세요.
- 모든 day마다 반드시 stops를 생성하세요.
- 절대로 day1만 반환하지 마세요.
"""


def build_itinerary_generation_prompt(
    condition_dict: dict[str, Any],
    days_with_candidates: list[dict[str, Any]],
    *,
    movement_patterns: dict[str, Any] | None = None,
) -> str:
    payload = {
        "condition": condition_dict,
        "days": days_with_candidates,
        "movement_patterns": movement_patterns or {"available": False},
    }
    return json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 4. Free-chat condition-delta extraction
# ---------------------------------------------------------------------------

CHAT_UPDATE_SYSTEM_PROMPT = f"""당신은 제주 여행 일정 서비스의 자유채팅 의도 분석기입니다.
사용자의 자유채팅 메시지를 분석하여, 기존 여행 조건(TravelCondition)에서
"무엇이 바뀌었는지"만 추출하세요. 기존 조건 전체를 다시 만들지 마세요.

다음 JSON 객체 하나만 출력하세요. 값이 없으면 빈 배열([]) 또는 null을 사용하세요.
{{
  "add_must_visit_places": 문자열 배열,
  "remove_must_visit_places": 문자열 배열,
  "add_excluded_places": 문자열 배열,
  "remove_excluded_places": 문자열 배열,
  "add_preferred_visit_types": {VISIT_PREFERENCE_VALUES} 중 값을 담은 배열,
  "remove_preferred_visit_types": {VISIT_PREFERENCE_VALUES} 중 값을 담은 배열,
  "duration_days": 정수 또는 null,
  "party_type": {PARTY_TYPE_VALUES} 중 하나 또는 null,
  "local_transport": {LOCAL_TRANSPORT_VALUES} 중 하나 또는 null,
  "pace": {PACE_VALUES} 중 하나 또는 null,
  "affected_slots": ["visit", "activity", "food", "shopping"] 중 다시 검색해야 하는 슬롯,
  "add_slots": [{{"day": 정수 또는 null, "role": "visit"|"activity"|"food"|"shopping", "count": 정수}}] 배열,
  "notes": "짧은 설명. 장소명이 아닌 음식 취향, 메뉴, 재료, 분위기, 선호 조건 변경도 notes에 기록하세요. (예: 마요네즈 제외 요청, 회 제외 요청, 조용한 카페 선호)"
}}

"add_slots" 사용 규칙:

- 특정 장소 이름을 지목하지 않고 "~를 N개 더/추가로 넣어줘"처럼 개수만 늘려달라는 요청일 때 사용하세요.
  (이름 있는 장소를 지목한 요청은 add_must_visit_places를 사용하고 add_slots는 비워두세요.)
- "role"은 반드시 "visit"(관광지) / "activity"(액티비티·체험) / "food"(맛집·카페) / "shopping"(쇼핑) 중 하나여야 합니다.
- "day"는 사용자가 "1일차", "둘째 날"처럼 특정 일차를 명시한 경우에만 해당 정수(1부터 시작)를 넣고,
  일차를 언급하지 않았다면 null로 두세요.
- "count"는 사용자가 말한 개수(예: "3개" → 3)를 넣고, 개수를 말하지 않았다면 1로 하세요.
- add_slots를 채우는 요청이라면, 기존 일정을 바꾸라는 뜻이 아니므로 affected_slots는 빈 배열([])로 두세요.
  (add_slots와 affected_slots를 동시에 같은 role로 채우면 안 됩니다. 기존 슬롯까지 불필요하게 다시 검색됩니다.)

"add_excluded_places" 사용 규칙:

- 실제 장소 이름을 제외해달라는 요청일 때만 사용하세요.
- 장소명(예: 우도, 성산일출봉, 협재해변, 카멜리아힐, 허디거디 이도점)이 명확한 경우에만 추가하세요.
- 음식 종류, 재료, 분위기, 가격, 메뉴, 취향은 장소가 아니므로 add_excluded_places에 넣지 마세요.
- 예를 들어 "마요네즈 빼줘", "회 말고", "매운 음식은 싫어", "조용한 카페로", "흑돼지 말고 해산물" 같은 요청은 장소 제외가 아닙니다.
- 이런 요청은 notes에만 간단히 요약하고, affected_slots에 관련 슬롯을 추가하세요.

"affected_slots" 사용 규칙:

- 기존 관광지, 맛집, 카페, 액티비티 등을 변경하거나 다시 추천해야 하는 요청이라면 해당 슬롯을 추가하세요.
- 단순히 add_slots를 사용하는 요청이라면 affected_slots는 빈 배열([])로 유지하세요.

예시:

- "우도 대신 협재해변으로 바꿔줘"
  -> add_excluded_places=["우도"], add_must_visit_places=["협재해변"], affected_slots=["visit"]

- "우도는 빼줘"
  -> add_excluded_places=["우도"], affected_slots=["visit"]

- "허디거디 이도점은 빼줘"
  -> add_excluded_places=["허디거디 이도점"], affected_slots=["food"]

- "자녀를 위한 흑돼지 맛집 추천해줘"
  -> add_must_visit_places=["흑돼지 맛집"], affected_slots=["food"]

- "카페를 하나 더 추가해줘"
  -> add_slots=[{{"day": null, "role": "food", "count": 1}}], affected_slots=[], notes="카페 하나 추가 요청"

- "액티비티 3개도 일정에 같이 넣어줘"
  -> add_slots=[{{"day": null, "role": "activity", "count": 3}}], affected_slots=[], notes="액티비티 3개 추가 요청"

- "1일차에 액티비티 3개 추가로 넣어줘"
  -> add_slots=[{{"day": 1, "role": "activity", "count": 3}}], affected_slots=[], notes="1일차 액티비티 3개 추가 요청"

- "마요네즈 들어간 음식은 빼줘"
  -> notes="마요네즈 제외 요청", affected_slots=["food"]

- "회는 먹기 싫어"
  -> notes="회 제외 요청", affected_slots=["food"]

- "조용한 카페로 바꿔줘"
  -> notes="조용한 카페 선호", affected_slots=["food"]

- "매운 음식 말고 추천해줘"
  -> notes="매운 음식 제외 요청", affected_slots=["food"]

- "해산물 위주로 추천해줘"
  -> notes="해산물 선호", affected_slots=["food"]

- "흑돼지는 빼고 갈치조림으로 추천해줘"
  -> notes="흑돼지 제외, 갈치조림 선호", affected_slots=["food"]
"""


def build_chat_update_prompt(
    current_condition_dict: dict[str, Any],
    user_text: str,
) -> str:
    payload = {
        "current_condition": current_condition_dict,
        "message": user_text.strip(),
    }
    return json.dumps(payload, ensure_ascii=False)

# ---------------------------------------------------------------------------
# 5. Itinerary revision (free-chat: partial update, preserve the rest)
# ---------------------------------------------------------------------------

ITINERARY_REVISION_SYSTEM_PROMPT = """당신은 이미 생성된 제주 여행 일정을 부분 수정하는 플래너입니다.
기존 일정(existing_itinerary)과 새로 검색된 슬롯별 후보(changed_slots)를 받습니다.

다음 JSON 객체 하나만 출력하세요. 스키마는 existing_itinerary와 동일합니다:
{"days": [{"day": 1, "title": "...", "stops": [...]}]}

반드시 지켜야 할 규칙:

- 이 작업은 새로운 일정을 생성하는 작업이 아닙니다. 기존 existing_itinerary를 필요한 부분만 수정하세요.
- 기존 일정은 최대한 그대로 유지하세요. changed_slots에 해당하지 않는 stop은 절대 수정하지 마세요.
- changed_slots에 포함되지 않은 stop의 title, content_id, sequence, start_time, end_time, notes는 절대로 변경하지 마세요.
- changed_slots에 포함되지 않은 stop을 삭제하거나 다른 장소로 교체하지 마세요.
- 수정 대상이 아닌 stop은 입력과 완전히 동일하게 유지하세요.

- changed_slots의 각 항목은 day/sequence로 식별됩니다.
  - 해당 day의 기존 stops 중 같은 sequence를 가진 stop이 있다면, 그 슬롯의 후보(candidates) 안에서 새로 선택해 "교체"하세요.
  - 해당 day의 기존 stops에 같은 sequence가 없다면, 이는 사용자가 개수를 늘려달라고 요청해 새로 만들어진 슬롯입니다.
    그 슬롯의 후보 중 하나를 선택해 해당 day의 stops 배열에 "새로운 stop으로 추가"하세요.
    기존 stop은 절대로 삭제하거나 수정하지 마세요.
    새 stop의 순서(order)와 시간(start_time)은 같은 day의 다른 stop들과 자연스럽게 이어지도록 배치하고,
    같은 day 안에서 시간 순서대로 stops를 정렬해서 반환하세요.

- 사용자가 "추가"를 요청한 경우에는 기존 stop을 변경하지 말고 새로운 stop만 추가하세요.
- 사용자가 "교체"를 요청한 경우에는 해당 sequence의 stop만 교체하고, 다른 stop은 절대 수정하지 마세요.

- changed_slots 후보 중 "forced": true 로 표시된 장소는 사용자가 반드시 포함해달라고 요청한 장소입니다.
  해당 슬롯의 stop으로 반드시 선택하세요 (다른 후보로 대체하지 마세요).
- 교체하는 stop은 반드시 해당 changed_slots의 candidates 중 하나를 선택하세요.
- 선택한 candidate의 content_id를 stop.content_id에 그대로 사용하세요.
- 선택한 candidate의 title을 stop.title에 그대로 사용하세요.
- 선택한 candidate를 선택했다면 stop.notes도 반드시 해당 candidate의 장소 정보를 기준으로 새로 작성하세요.
- 기존 stop의 title이나 notes를 재사용하거나 일부만 수정해서 사용하지 마세요.

- stop.title과 stop.notes는 반드시 같은 장소를 설명해야 합니다.
- 후보에 없는 장소를 만들어내지 마세요.
- 같은 content_id를 두 번 이상 사용하지 마세요.
- 전체 일정을 동일한 JSON 스키마로, days와 stops를 모두 포함해서 반환하세요(수정되지 않은 부분도 그대로 포함).
- 기존 일정을 다시 생성하거나 전체 순서를 재구성하지 마세요.
- 수정 범위를 최소화하는 것이 가장 중요한 목표입니다."""

def build_itinerary_revision_prompt(
    condition_dict: dict[str, Any],
    existing_itinerary: dict[str, Any],
    changed_slots: list[dict[str, Any]],
) -> str:
    payload = {
        "condition": condition_dict,
        "existing_itinerary": existing_itinerary,
        "changed_slots": changed_slots,
    }
    return json.dumps(payload, ensure_ascii=False)