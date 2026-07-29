from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Mapping

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rag import create_rag_orchestrator


PARTY_TYPES = {
    "혼자": "solo",
    "친구·연인 2명": "non_family_two",
    "친구·지인 단체": "non_family_group",
    "가족 2명": "family_two",
    "가족 단체": "family_group",
    "아이 동반": "with_children",
    "부모님 동반": "with_parents",
    "3대 가족": "three_generations",
}
TRANSPORTS = {
    "렌터카": "rental_car",
    "자가용": "own_car",
    "대중교통": "public_transit",
    "택시": "taxi",
    "혼합": "mixed",
}
VISIT_TYPES = {
    "자연": "nature",
    "역사": "history",
    "문화": "culture",
    "시장·쇼핑": "market_shopping",
    "레저": "leisure",
    "테마파크": "theme_park",
    "트레일": "trail",
    "축제": "festival",
    "체험": "experience",
}
PACES = {
    "여유롭게": "relaxed",
    "보통": "balanced",
    "촘촘하게": "packed",
}
MEAL_LABELS = {
    "breakfast": "아침",
    "lunch": "점심",
    "dinner": "저녁",
}
VALIDATION_HELP = {
    "distance_limit": (
        "연속 장소 사이의 거리가 사용자의 이동거리 제한보다 깁니다.",
        "긴 이동 피하기를 해제하거나 시작 지점과 가까운 후보로 다시 생성해 보세요.",
    ),
    "destination_distance_limit": (
        "마지막 장소에서 종료 지점·공항까지의 거리가 제한보다 깁니다.",
        "종료 지점과 가까운 마지막 장소가 필요합니다.",
    ),
    "destination_time_limit": (
        "마지막 장소에서 공항으로 이동하면 도착 제한 시각을 넘습니다.",
        "마지막 일정을 앞당기거나 더 가까운 장소로 바꿔야 합니다.",
    ),
    "outside_time_slot": (
        "장소의 체류시간 또는 운영시간이 아침·오전·점심·오후·저녁 슬롯과 맞지 않습니다.",
        "체류시간이 짧거나 해당 시간대에 운영하는 후보가 필요합니다.",
    ),
    "day_time_limit": (
        "일정 종료 시각이 하루 또는 공항 도착 제한 시각을 넘습니다.",
        "체류시간을 줄이거나 일부 장소를 교체해야 합니다.",
    ),
    "missing_slot": (
        "필요한 일정 슬롯에 선택된 장소가 없습니다.",
        "검색 범위를 넓히거나 해당 슬롯을 제외해야 합니다.",
    ),
    "missing_required_place": (
        "반드시 포함하도록 지정한 장소가 최종 일정에 없습니다.",
        "필수 장소의 이름과 TourAPI 후보 존재 여부를 확인해 주세요.",
    ),
    "missing_required_day_place": (
        "지정한 일차에 필수 장소가 배치되지 않았습니다.",
        "해당 일차의 검색 권역이나 필수 장소 이름을 확인해 주세요.",
    ),
    "not_whitelisted": (
        "LLM이 TourAPI 후보 목록에 없는 장소 ID를 선택했습니다.",
        "화이트리스트 안의 후보로 자동 수정되어야 합니다.",
    ),
    "duplicate_place": (
        "같은 장소가 일정에 두 번 선택되었습니다.",
        "중복되지 않는 다른 TourAPI 후보가 필요합니다.",
    ),
    "meal_slot_requires_restaurant": (
        "식사 시간에 음식점이 아닌 장소가 선택되었습니다.",
        "해당 시간대의 음식점 후보를 다시 검색해야 합니다.",
    ),
    "food_or_cafe_not_allowed": (
        "관광지 슬롯에 음식점 또는 카페가 선택되었습니다.",
        "관광 가능한 TourAPI 후보로 교체해야 합니다.",
    ),
}


def _state() -> None:
    defaults = {
        "rag_result": None,
        "conversation": [],
        "last_error": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


@st.cache_resource(show_spinner=False)
def _rag():
    return create_rag_orchestrator(project_root=PROJECT_ROOT)


def _csv(text: str) -> list[str]:
    return [
        item.strip()
        for item in text.replace("\n", ",").split(",")
        if item.strip()
    ]


def _day_requirements(text: str) -> list[dict[str, Any]]:
    """Parse `2: 우도, 성산일출봉; 3: 한라수목원`."""

    result: list[dict[str, Any]] = []
    for block in text.split(";"):
        block = block.strip()
        if not block:
            continue
        day_text, separator, places_text = block.partition(":")
        if not separator:
            raise ValueError(
                "일차별 필수 장소는 '2: 우도, 성산일출봉' 형식으로 입력하세요."
            )
        day = int(day_text.strip().replace("Day", "").replace("일차", ""))
        places = _csv(places_text)
        if day < 1 or not places:
            raise ValueError("일차와 장소를 모두 입력하세요.")
        result.append({"day": day, "place_names": places})
    return result


def _execute_initial(options: Mapping[str, Any], message: str) -> None:
    try:
        with st.spinner("AIHub 동선과 TourAPI 후보를 검색하고 있습니다..."):
            result = _rag().run(
                selected_options=options,
                message=message.strip(),
            )
        st.session_state.rag_result = result
        st.session_state.conversation = []
        if message.strip():
            st.session_state.conversation.append(
                {"role": "user", "content": message.strip()}
            )
        _remember_assistant(result)
        st.session_state.last_error = None
    except Exception as exc:
        st.session_state.last_error = f"{type(exc).__name__}: {exc}"


def _remember_assistant(result: Mapping[str, Any]) -> None:
    message = str(result.get("message") or "").strip()
    if message:
        st.session_state.conversation.append(
            {"role": "assistant", "content": message}
        )


def _continue_with_selection(selected_options: Mapping[str, Any]) -> None:
    previous = st.session_state.rag_result or {}
    try:
        with st.spinner("선택 내용을 반영해 다시 생성하고 있습니다..."):
            result = _rag().run(
                selected_options=selected_options,
                current_conditions=previous.get("conditions"),
            )
        st.session_state.rag_result = result
        st.session_state.conversation.append(
            {
                "role": "user",
                "content": f"선택 입력: {dict(selected_options)}",
            }
        )
        _remember_assistant(result)
        st.session_state.last_error = None
    except Exception as exc:
        st.session_state.last_error = f"{type(exc).__name__}: {exc}"


def _continue_with_text(message: str) -> None:
    previous = st.session_state.rag_result or {}
    history = list(st.session_state.conversation)
    try:
        with st.spinner("요청을 처리하고 있습니다..."):
            if previous.get("status") == "completed":
                result = _rag().revise(
                    previous_result=previous,
                    message=message,
                )
            else:
                result = _rag().run(
                    message=message,
                    history=history,
                    current_conditions=previous.get("conditions"),
                )
        st.session_state.rag_result = result
        st.session_state.conversation.append(
            {"role": "user", "content": message}
        )
        _remember_assistant(result)
        st.session_state.last_error = None
    except Exception as exc:
        st.session_state.last_error = f"{type(exc).__name__}: {exc}"


def _render_input_form() -> None:
    st.subheader("1. 최초 여행 조건")
    st.caption(
        "말풍선을 눌러 조건을 선택하세요. 선택된 말풍선은 강조되어 표시됩니다."
    )
    st.info(
        "처리 순서: 조건 선택 → AIHub 유사 동선 구성 → TourAPI 장소 검색 "
        "→ 일정 생성 → 거리·운영시간·중복·필수 장소 검증"
    )
    with st.form("initial_conditions", clear_on_submit=False):
        top1, top2 = st.columns([1, 2])
        with top1:
            duration_days = st.number_input(
                "여행 일수",
                min_value=1,
                max_value=30,
                value=2,
            )
            companion_count = st.number_input(
                "총 여행 인원",
                min_value=1,
                max_value=30,
                value=2,
            )
        with top2:
            st.info(
                "필수 조건은 동행 유형, 교통수단, 선호 관광 유형입니다. "
                "관광 유형은 여러 개를 선택할 수 있습니다."
            )

        st.markdown("##### 누구와 함께 여행하나요?")
        party_label = st.pills(
            "동행 유형",
            list(PARTY_TYPES),
            default="친구·연인 2명",
            required=True,
            label_visibility="collapsed",
            width="stretch",
        )

        st.markdown("##### 제주에서 어떤 교통수단을 이용하나요?")
        transport_label = st.pills(
            "교통수단",
            list(TRANSPORTS),
            default="렌터카",
            required=True,
            label_visibility="collapsed",
            width="stretch",
        )

        st.markdown("##### 어떤 관광지를 좋아하나요?")
        visit_labels = st.pills(
            "선호 관광 유형",
            list(VISIT_TYPES),
            selection_mode="multi",
            default=["자연", "문화"],
            label_visibility="collapsed",
            width="stretch",
        )

        st.markdown("##### 원하는 일정 속도는 어떤가요?")
        pace_label = st.pills(
            "일정 속도",
            list(PACES),
            default="여유롭게",
            required=True,
            label_visibility="collapsed",
            width="stretch",
        )

        st.markdown("##### 추가로 반영할 조건을 선택하세요.")
        extra_conditions = st.pills(
            "추가 조건",
            ["주차 가능한 장소", "긴 이동 피하기", "아침 식사 일정 포함"],
            selection_mode="multi",
            default=["주차 가능한 장소", "긴 이동 피하기"],
            label_visibility="collapsed",
            width="stretch",
        )
        parking_required = "주차 가능한 장소" in extra_conditions
        avoid_long_distance = "긴 이동 피하기" in extra_conditions
        include_breakfast = "아침 식사 일정 포함" in extra_conditions

        food_col, blank_col = st.columns([2, 1])
        with food_col:
            preferred_foods = st.text_input(
                "선호 메뉴",
                placeholder="갈치조림, 흑돼지",
            )
        with blank_col:
            st.caption(
                "메뉴를 비워두면 RAG가 식사 후보 부족 시 추가로 질문합니다."
            )

        with st.expander("선택 조건"):
            opt1, opt2 = st.columns(2)
            with opt1:
                start_point = st.text_input(
                    "시작 지점",
                    value="제주국제공항",
                )
                trip_start_time = st.text_input(
                    "첫날 시작 시각",
                    value="09:00",
                    help="HH:MM 형식",
                )
                accommodation = st.text_input(
                    "숙소명 또는 주소",
                    placeholder="입력하지 않아도 됩니다.",
                )
                preferred_places = st.text_input(
                    "좋아하는 장소",
                    placeholder="숲, 바다",
                )
            with opt2:
                end_point = st.text_input(
                    "종료 지점·공항",
                    value="제주국제공항",
                )
                deadline = st.text_input(
                    "마지막 날 도착 제한 시각",
                    value="20:00",
                    help="HH:MM 형식",
                )
                must_visit = st.text_input(
                    "반드시 포함할 장소",
                    placeholder="우도, 성산일출봉",
                )
                excluded_places = st.text_input(
                    "제외할 장소",
                    placeholder="테마파크",
                )
            required_by_day = st.text_input(
                "일차별 필수 장소",
                placeholder="2: 우도, 성산일출봉; 3: 한라수목원",
            )

        natural_message = st.text_area(
            "추가 자연어 요청",
            placeholder=(
                "예: 부모님과 여유롭게 여행하고 싶고, "
                "휠체어 이동이 어려운 곳은 피해주세요."
            ),
        )
        submitted = st.form_submit_button(
            "RAG 일정 생성",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not visit_labels:
            st.error("선호 관광 유형을 한 개 이상 선택해 주세요.")
            return
        try:
            options = {
                "region": "제주",
                "duration_days": int(duration_days),
                "party_type": PARTY_TYPES[party_label],
                "companion_count": int(companion_count),
                "local_transport": TRANSPORTS[transport_label],
                "preferred_visit_types": [
                    VISIT_TYPES[label] for label in visit_labels
                ],
                "pace": PACES[pace_label],
                "parking_required": parking_required,
                "avoid_long_distance": avoid_long_distance,
                "include_breakfast": include_breakfast,
                "preferred_foods": _csv(preferred_foods),
                "entry_point": start_point.strip() or None,
                "arrival_time": trip_start_time.strip() or None,
                "exit_point": end_point.strip() or None,
                "departure_time": deadline.strip() or None,
                "accommodation_address": accommodation.strip() or None,
                "preferred_places": _csv(preferred_places),
                "must_visit_places": _csv(must_visit),
                "excluded_places": _csv(excluded_places),
                "required_day_itineraries": _day_requirements(
                    required_by_day
                ),
            }
        except ValueError as exc:
            st.error(str(exc))
            return
        _execute_initial(options, natural_message)
        st.rerun()


def _status_label(status: str) -> str:
    labels = {
        "completed": "완료",
        "clarification_required": "추가 입력 필요",
        "retrieval_incomplete": "검색 후보 부족",
        "validation_failed": "검증 실패",
        "replacement_unavailable": "교체 후보 없음",
        "no_reference_pattern": "유사 동선 없음",
        "no_route_slots": "동선 슬롯 없음",
    }
    return labels.get(status, status or "결과 없음")


def _render_summary(result: Mapping[str, Any]) -> None:
    status = str(result.get("status") or "")
    st.subheader("2. 실행 결과")
    if status == "completed":
        st.success(f"상태: {_status_label(status)}")
    elif status == "clarification_required":
        st.warning(f"상태: {_status_label(status)}")
    else:
        st.error(f"상태: {_status_label(status)}")

    if result.get("message"):
        st.write(result["message"])

    if status == "validation_failed":
        st.warning(
            "장소 후보와 시간표는 만들어졌지만 안전 규칙을 통과하지 못했습니다. "
            "아래 일정은 확정 일정이 아니라 실패 원인을 확인하기 위한 미리보기입니다."
        )
        _render_validation_issues(result)

    conditions = result.get("conditions") or {}
    meta = result.get("meta") or {}
    route_strategy = meta.get("route_strategy")
    if route_strategy == "tourapi_only_fallback":
        reason_labels = {
            "no_reference_pattern": "유사한 AIHub 여행 동선을 찾지 못함",
            "no_route_slots": "AIHub 여행에는 사용할 수 있는 동선 슬롯이 없음",
        }
        fallback_reason = reason_labels.get(
            str(meta.get("aihub_fallback_reason") or ""),
            "AIHub 동선 사용 불가",
        )
        st.warning(
            f"데이터 경로: TourAPI 단독 폴백 — {fallback_reason}. "
            "AIHub 방문 순서·체류시간은 사용하지 않고 TourAPI 장소와 "
            "거리·운영시간만으로 일정을 구성했습니다."
        )
    elif meta.get("aihub_used"):
        st.info(
            "데이터 경로: AIHub 유사 동선의 권역·방문 순서를 참고하고, "
            "실제 장소는 TourAPI 후보에서 선택했습니다."
        )
        if status == "retrieval_incomplete":
            st.caption(
                "현재는 AIHub 동선이 존재하므로 TourAPI 단독 폴백을 사용하지 "
                "않았습니다. 일부 슬롯에서 조건을 만족하는 TourAPI 장소가 "
                "부족한 상태입니다."
            )

    a, b, c, d = st.columns(4)
    a.metric("여행 일수", conditions.get("duration_days") or "-")
    b.metric("일정 항목", len(result.get("itinerary") or []))
    c.metric("하루 관광지", meta.get("tourism_places_per_day", 3))
    d.metric(
        "LLM 일정 생성",
        "사용" if meta.get("llm_itinerary_used") else "미사용/대체",
    )


def _render_validation_issues(result: Mapping[str, Any]) -> None:
    validation = result.get("validation") or {}
    issues = validation.get("issues") or []
    if not issues:
        st.error(
            "상세 검증 항목이 응답에 없습니다. 전체 RAG 응답 JSON을 확인해 주세요."
        )
        return

    st.markdown("#### 검증에 실패한 이유")
    for issue in issues:
        code = str(issue.get("code") or "unknown")
        reason, action = VALIDATION_HELP.get(
            code,
            (
                "일정이 현재 검증 규칙을 충족하지 못했습니다.",
                "상세 메시지를 확인해 조건이나 후보를 조정해 주세요.",
            ),
        )
        day = issue.get("day")
        location = f"Day {day}" if day else "전체 일정"
        st.error(f"**{location} · {code}** — {reason}")
        message = str(issue.get("message") or "").strip()
        if message:
            st.caption(f"검증 상세: {message}")
        st.caption(f"해결 방향: {action}")


def _render_clarification(result: Mapping[str, Any]) -> None:
    questions = result.get("clarification_questions") or []
    if questions:
        st.markdown("#### RAG의 추가 질문")
        for question in questions:
            st.info(str(question))

    options = result.get("clarification_options") or []
    if not options:
        return
    st.markdown("#### 선택지")
    columns = st.columns(min(len(options), 3))
    for index, option in enumerate(options):
        label = str(option.get("label") or option.get("value") or "선택")
        description = str(option.get("description") or "")
        with columns[index % len(columns)]:
            st.caption(description)
            if st.button(
                label,
                key=f"clarification_{index}_{option.get('value')}",
                use_container_width=True,
            ):
                selected = option.get("selected_options") or {}
                if selected:
                    _continue_with_selection(selected)
                    st.rerun()
                else:
                    st.info("아래 자연어 입력창에 메뉴나 지역을 입력해 주세요.")


def _render_itinerary(result: Mapping[str, Any]) -> None:
    itinerary = result.get("itinerary") or []
    if not itinerary:
        return
    if result.get("status") == "validation_failed":
        st.markdown("#### 검증 전 일정 미리보기")
    else:
        st.markdown("#### 생성 일정")
    st.caption(
        "굵은 글씨는 시간과 장소, 초록 표시는 관광지·식사 유형입니다. "
        "아래에 장소 소개, 선택 이유와 이전 장소로부터의 이동거리가 표시됩니다."
    )
    days = sorted({int(item.get("day") or 0) for item in itinerary})
    tabs = st.tabs([f"Day {day}" for day in days])
    for tab, day in zip(tabs, days):
        with tab:
            for item in itinerary:
                if int(item.get("day") or 0) != day:
                    continue
                meal_type = item.get("meal_type")
                kind = MEAL_LABELS.get(str(meal_type), "관광지")
                title = item.get("title") or "(이름 없음)"
                start = item.get("start_time") or "--:--"
                end = item.get("end_time") or "--:--"
                st.markdown(f"**{start}~{end} · {title}** `{kind}`")
                description = str(item.get("description") or "").strip()
                if description:
                    st.write(description)
                selection_reason = str(
                    item.get("selection_reason")
                    or item.get("reason")
                    or ""
                ).strip()
                if selection_reason:
                    st.caption(f"선택 이유: {selection_reason}")
                distance = item.get("distance_from_previous_km")
                if isinstance(distance, (int, float)):
                    route_verified = bool(item.get("route_verified"))
                    distance_label = (
                        "도로 이동거리" if route_verified else "추정 이동거리"
                    )
                    st.caption(
                        f"이전 장소에서 {distance_label} {distance:.1f}km"
                    )
                st.divider()


def _render_diagnostics(result: Mapping[str, Any]) -> None:
    with st.expander("조건·검증 정보"):
        left, right = st.columns(2)
        with left:
            st.markdown("**정규화된 조건**")
            st.json(result.get("conditions") or {})
        with right:
            st.markdown("**검증 결과**")
            st.json(result.get("validation") or {})
    with st.expander("전체 RAG 응답 JSON"):
        st.json(result)

    slots = result.get("slot_candidates") or []
    if slots:
        rows = []
        for item in slots:
            slot = item.get("slot") or {}
            rows.append(
                {
                    "day": slot.get("day"),
                    "sequence": slot.get("sequence"),
                    "kind": slot.get("slot_kind"),
                    "meal": slot.get("meal_type"),
                    "query": item.get("query"),
                    "candidate_count": len(item.get("candidates") or []),
                }
            )
        with st.expander("검색 슬롯별 후보 수"):
            st.dataframe(pd.DataFrame(rows), use_container_width=True)


def _render_conversation() -> None:
    conversation = st.session_state.conversation
    if conversation:
        with st.expander("후속 요청 기록"):
            for item in conversation:
                label = "사용자" if item["role"] == "user" else "RAG"
                st.markdown(f"**{label}:** {item['content']}")


def main() -> None:
    st.set_page_config(
        page_title="RAG 임시 테스트",
        page_icon="🧪",
        layout="wide",
    )
    st.markdown(
        """
        <style>
        div[data-testid="stPills"] button {
            border-radius: 999px !important;
            padding: 0.45rem 1rem !important;
            border-width: 1px !important;
            box-shadow: 0 2px 8px rgba(20, 90, 70, 0.08);
        }
        div[data-testid="stPills"] button:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(20, 90, 70, 0.14);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    _state()
    st.title("🧪 제주 여행 RAG 임시 테스트")
    st.caption(
        "src/rag의 순수 Python 인터페이스를 직접 호출합니다. "
        "backend에는 연결하지 않습니다."
    )

    with st.sidebar:
        st.markdown("### 테스트 제어")
        if st.button("결과 초기화", use_container_width=True):
            st.session_state.rag_result = None
            st.session_state.conversation = []
            st.session_state.last_error = None
            st.rerun()
        st.info(
            "테스트가 끝나면 `rag_test_frontend` 폴더만 삭제하면 됩니다."
        )

    _render_input_form()

    if st.session_state.last_error:
        st.error(st.session_state.last_error)

    result = st.session_state.rag_result
    if result:
        _render_summary(result)
        _render_clarification(result)
        _render_itinerary(result)
        _render_diagnostics(result)
        _render_conversation()

        prompt = st.chat_input(
            (
                "예: 그냥 식사 장소를 빼 주세요. / "
                "2일차 우도를 다른 곳으로 교체해 주세요."
            )
        )
        if prompt:
            _continue_with_text(prompt)
            st.rerun()


if __name__ == "__main__":
    main()
