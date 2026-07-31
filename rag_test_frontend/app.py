from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Mapping

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rag import (
    EvalCase,
    OpenAIItineraryJudge,
    OpenAIResponseComparator,
    build_report,
    create_langgraph_rag_workflow,
    evaluate_case,
    load_eval_cases,
    report_as_markdown,
    start_guided_dialogue,
    submit_guided_answer,
    summarize_answer_comparisons,
)
EVAL_DATASET = PROJECT_ROOT / "evals" / "rag" / "golden_cases.jsonl"
MENU_RAG_TEST = "일정 생성 테스트"
MENU_EVALUATION = "RAG 평가"

COMPARISON_QUESTION_SAMPLES = {
    "01. 부모님·렌터카·자연 문화": (
        "부모님과 렌터카로 제주 2박 3일 여행을 갑니다. 자연과 문화 장소를 "
        "좋아하고 긴 이동은 피하고 싶습니다. 주차 가능한 관광지를 하루 "
        "3곳씩 추천해 주세요."
    ),
    "02. 연인·동부권·3박 4일": (
        "연인과 제주 동부권을 중심으로 3박 4일 여행하려고 합니다. 렌터카를 "
        "이용하고 바다, 숲, 체험 장소를 좋아합니다. 매일 관광지 3곳과 "
        "점심·저녁 식사 장소를 포함해 주세요."
    ),
    "03. 아이 동반·비 오는 날": (
        "7살 아이와 제주에서 2일 여행합니다. 비가 올 예정이라 실내 관광지와 "
        "체험 장소를 우선하고, 렌터카로 이동하며 하루 3곳씩 추천해 주세요."
    ),
    "04. 혼자·대중교통": (
        "혼자 제주 2박 3일 여행을 갑니다. 대중교통으로 이동하고 시장, 역사, "
        "해안 풍경을 좋아합니다. 버스로 이동하기 쉬운 장소를 하루 3곳씩 "
        "일정으로 만들어 주세요."
    ),
    "05. 휠체어 접근성 필수": (
        "휠체어를 사용하는 가족과 렌터카로 제주 2박 3일 여행합니다. 계단과 "
        "급경사를 피하고 주차장과 휠체어 접근성이 확인되는 관광지를 하루 "
        "3곳씩 추천해 주세요."
    ),
    "06. 필수 장소·일자 지정": (
        "제주 3박 4일 렌터카 여행을 계획해 주세요. 2일 차에는 반드시 "
        "성산일출봉을 포함하고, 자연과 역사 관광지를 하루 3곳씩 배치해 "
        "주세요."
    ),
    "07. 오름·카페 제외": (
        "부모님과 제주 서부에서 2박 3일 여행합니다. 렌터카를 이용하며 오름, "
        "등산, 카페는 제외하고 숲과 문화 관광지를 하루 3곳씩 추천해 주세요."
    ),
    "08. 공항 도착·출발 시간 제한": (
        "첫날 13시에 제주국제공항에서 렌터카 여행을 시작하고, 3일 차 "
        "15시까지 제주국제공항에 도착해야 합니다. 2박 3일 동안 무리 없는 "
        "관광지를 하루 3곳씩 배치해 주세요."
    ),
    "09. 숙소 출발·복귀": (
        "서귀포시 중문동 숙소에서 매일 출발하고 돌아오는 3일 일정을 만들어 "
        "주세요. 렌터카를 이용하고 폭포, 숲, 박물관을 선호하며 하루 관광지는 "
        "3곳이면 좋겠습니다."
    ),
    "10. 짧은 이동 우선": (
        "70대 부모님 두 분과 제주에서 렌터카로 2일 여행합니다. 장소 사이 "
        "이동은 가능하면 30분 이내로 하고, 오래 걷지 않는 관광지를 하루 "
        "3곳씩 추천해 주세요."
    ),
    "11. 우천 대체 일정 포함": (
        "친구 3명과 제주 3박 4일 렌터카 여행을 갑니다. 자연과 레저를 "
        "좋아합니다. 기본 일정과 함께 비가 올 때 교체할 실내 장소도 날짜별로 "
        "제안해 주세요."
    ),
    "12. 식사 일정 제외": (
        "제주 2박 3일 가족 여행 일정을 만들어 주세요. 렌터카를 이용하고 "
        "자연과 체험 관광지를 좋아합니다. 식당과 카페는 일정에서 빼고 관광지 "
        "3곳만 날짜별로 추천해 주세요."
    ),
    "13. 채식 메뉴·아침 포함": (
        "연인과 제주 2박 3일 여행합니다. 렌터카를 이용하고 아침 식사도 "
        "일정에 포함해 주세요. 식사는 채식 메뉴가 있는 곳을 우선하고, "
        "관광지는 자연과 문화를 하루 3곳씩 추천해 주세요."
    ),
    "14. 예산 제한": (
        "친구 2명과 제주에서 3일 동안 렌터카 여행을 합니다. 1인당 관광과 "
        "식사 예산은 하루 10만원이며, 해변과 체험 장소를 하루 3곳씩 포함한 "
        "일정을 만들어 주세요."
    ),
    "15. 반려견 동반": (
        "반려견과 함께 제주 2박 3일 렌터카 여행을 갑니다. 반려견 출입과 "
        "주차가 가능한 자연 관광지를 중심으로 하루 3곳씩 추천해 주세요. "
        "확인되지 않은 출입 가능 여부는 명확히 표시해 주세요."
    ),
    "16. 제주 하루 핵심 코스": (
        "제주국제공항에서 오전 9시에 출발해 오후 7시에 돌아오는 당일치기 "
        "렌터카 코스를 만들어 주세요. 전통시장, 문화 관광지, 바다를 각각 "
        "한 곳씩 포함해 주세요."
    ),
    "17. 4박 5일 권역 순환": (
        "렌터카로 제주 4박 5일 여행을 합니다. 제주시에서 시작해 동부, 남부, "
        "서부를 한 방향으로 이동하고 마지막 날 제주공항으로 돌아오도록 매일 "
        "관광지 3곳씩 구성해 주세요."
    ),
    "18. 운영시간 엄격 반영": (
        "월요일부터 제주 2박 3일 여행을 갑니다. 렌터카를 이용하며 박물관과 "
        "정원을 좋아합니다. 실제 방문 날짜의 휴무일과 운영시간을 확인할 수 "
        "있는 장소만 하루 3곳씩 추천해 주세요."
    ),
    "19. 특정 일정 부분 수정": (
        "기존 제주 3일 일정 중 2일 차 오후의 성산일출봉만 실내 문화 "
        "관광지로 교체해 주세요. 다른 날짜와 장소는 변경하지 말아 주세요."
    ),
    "20. 정보 부족·재질문 평가": (
        "이번 주말에 제주 여행을 가려고 합니다. 저에게 맞는 일정을 추천해 "
        "주세요."
    ),
}


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
TRAVEL_STYLES = {
    "힐링·여유": "healing",
    "자연·풍경": "nature",
    "역사·문화": "culture",
    "체험·액티비티": "activity",
    "시장·로컬": "local",
    "인기 명소 중심": "popular",
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
        "guided_dialogue": None,
        "conversation": [],
        "last_error": None,
        "evaluation_artifact": None,
        "evaluation_error": None,
        "comparison_artifact": None,
        "comparison_error": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


@st.cache_resource(show_spinner=False)
def _rag():
    return create_langgraph_rag_workflow(project_root=PROJECT_ROOT)


@st.cache_data(show_spinner=False)
def _evaluation_cases(dataset_path: str) -> list[EvalCase]:
    return load_eval_cases(dataset_path)


def _condition_evaluation_result(
    orchestrator: Any,
    case: EvalCase,
) -> dict[str, Any]:
    if case.selected_options:
        base = orchestrator.condition_service.from_selections(
            selected_options=case.selected_options,
            current_conditions=case.current_conditions,
        )
        if case.message.strip():
            value = orchestrator.condition_service.extract(
                message=case.message,
                history=case.history,
                current_conditions=base.conditions,
            )
        else:
            value = base
    else:
        value = orchestrator.condition_service.extract(
            message=case.message,
            history=case.history,
            current_conditions=case.current_conditions,
        )
    return {
        "status": (
            "conditions_ready" if value.ready else "clarification_required"
        ),
        **value.to_dict(),
    }


def _run_evaluation_case(
    orchestrator: Any,
    case: EvalCase,
) -> dict[str, Any]:
    if case.stage == "conditions":
        return _condition_evaluation_result(orchestrator, case)
    return orchestrator.run(
        message=case.message,
        history=case.history,
        current_conditions=case.current_conditions,
        selected_options=case.selected_options or None,
    )


def _drain_usage(orchestrator: Any) -> list[dict[str, Any]]:
    drain = getattr(orchestrator.llm, "drain_usage_records", None)
    return drain() if callable(drain) else []


def _usage_summary(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    by_stage: dict[str, dict[str, int]] = {}
    for record in records:
        stage = str(record.get("stage") or "unknown")
        bucket = by_stage.setdefault(
            stage,
            {
                "calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "reasoning_tokens": 0,
                "input_characters": 0,
                "output_token_budget": 0,
            },
        )
        bucket["calls"] += 1
        for name in (
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "reasoning_tokens",
            "input_characters",
            "output_token_budget",
        ):
            bucket[name] += int(record.get(name) or 0)
    return {
        "calls": len(records),
        "input_tokens": sum(
            int(item.get("input_tokens") or 0) for item in records
        ),
        "output_tokens": sum(
            int(item.get("output_tokens") or 0) for item in records
        ),
        "total_tokens": sum(
            int(item.get("total_tokens") or 0) for item in records
        ),
        "reasoning_tokens": sum(
            int(item.get("reasoning_tokens") or 0) for item in records
        ),
        "input_characters": sum(
            int(item.get("input_characters") or 0) for item in records
        ),
        "output_token_budget": sum(
            int(item.get("output_token_budget") or 0) for item in records
        ),
        "by_stage": by_stage,
    }


def _run_selected_evaluation(
    *,
    cases: list[EvalCase],
    repeat: int,
    case_score: float,
    pass_rate: float,
    llm_judge: bool,
    judge_model: str,
) -> dict[str, Any]:
    orchestrator = _rag()
    discarded_usage = _drain_usage(orchestrator)
    judge = (
        OpenAIItineraryJudge(model=judge_model.strip() or None)
        if llm_judge
        else None
    )
    evaluations = []
    generation_usage: list[dict[str, Any]] = []
    total_runs = len(cases) * repeat
    progress = st.progress(0, text="평가를 준비하고 있습니다.")
    completed_runs = 0

    for repeat_index in range(repeat):
        for case in cases:
            evaluation_case = (
                case
                if repeat == 1
                else replace(
                    case,
                    case_id=f"{case.case_id}#{repeat_index + 1}",
                )
            )
            progress.progress(
                completed_runs / total_runs,
                text=(
                    f"{evaluation_case.case_id} 실행 중 "
                    f"({completed_runs + 1}/{total_runs})"
                ),
            )
            started = time.perf_counter()
            result = _run_evaluation_case(orchestrator, case)
            latency_ms = (time.perf_counter() - started) * 1000
            generation_usage.extend(_drain_usage(orchestrator))
            evaluations.append(
                evaluate_case(
                    evaluation_case,
                    result,
                    latency_ms=latency_ms,
                    judge=judge,
                    pass_threshold=case_score,
                )
            )
            completed_runs += 1
            progress.progress(
                completed_runs / total_runs,
                text=f"평가 진행 {completed_runs}/{total_runs}",
            )

    progress.empty()
    report = build_report(evaluations, pass_threshold=pass_rate)
    judge_usage = [
        dict(evaluation.judge.usage)
        for evaluation in evaluations
        if evaluation.judge is not None
    ]
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "dataset": str(EVAL_DATASET),
        "repeat": repeat,
        "llm_judge": llm_judge,
        "judge_model": judge_model.strip() if llm_judge else None,
        "generation_usage": _usage_summary(generation_usage),
        "discarded_preexisting_usage": _usage_summary(discarded_usage),
        "judge_usage": _usage_summary(judge_usage),
        "report": report.to_dict(),
        "markdown": report_as_markdown(report),
    }


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


def _execute_initial(
    *,
    duration_days: int,
    party_size: int,
    local_transport: str,
    travel_style: str,
) -> None:
    try:
        with st.spinner("AIHub 동선과 TourAPI 후보를 검색하고 있습니다..."):
            result = _rag().create_initial_itinerary(
                duration_days=duration_days,
                party_size=party_size,
                local_transport=local_transport,
                travel_style=travel_style,
            )
        st.session_state.rag_result = result
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
                result = _rag().continue_itinerary(
                    previous_result=previous,
                    message=message,
                    history=history,
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


def _ensure_guided_dialogue() -> Mapping[str, Any]:
    state = st.session_state.guided_dialogue
    if not isinstance(state, Mapping):
        state = start_guided_dialogue()
        st.session_state.guided_dialogue = state
        st.session_state.conversation = [
            {"role": "assistant", "content": state["question"]}
        ]
    return state


def _submit_guided_value(value: str, *, display_value: str | None = None) -> None:
    current = _ensure_guided_dialogue()
    next_state = submit_guided_answer(current, value)
    st.session_state.guided_dialogue = next_state
    st.session_state.conversation.append(
        {"role": "user", "content": display_value or str(value)}
    )
    error = str(next_state.get("error") or "").strip()
    if error:
        st.session_state.conversation.append(
            {
                "role": "assistant",
                "content": f"{error}\n\n{next_state['question']}",
            }
        )
        return
    if next_state.get("ready"):
        inputs = dict(next_state["generation_inputs"])
        st.session_state.conversation.append(
            {
                "role": "assistant",
                "content": (
                    "좋습니다. 입력하신 조건으로 AIHub 동선과 TourAPI 장소를 "
                    "검색해 1차 여행 일정을 만들겠습니다."
                ),
            }
        )
        _execute_initial(**inputs)
        return
    st.session_state.conversation.append(
        {"role": "assistant", "content": next_state["question"]}
    )


def _render_guided_intake() -> None:
    state = _ensure_guided_dialogue()
    st.subheader("제주 여행 조건 대화")
    st.caption(
        "RAG가 한 번에 한 가지씩 질문합니다. 선택지를 누르거나 아래 "
        "대화창에 직접 답변할 수 있습니다."
    )
    _render_conversation()
    if state.get("ready"):
        return
    options = list(state.get("options") or [])
    if options:
        st.markdown("##### 빠른 선택")
        columns = st.columns(min(3, len(options)))
        for index, option in enumerate(options):
            label = str(option["label"])
            value = str(option["value"])
            with columns[index % len(columns)]:
                if st.button(
                    label,
                    key=f"guided_{state['step_index']}_{value}",
                    use_container_width=True,
                ):
                    _submit_guided_value(value, display_value=label)
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
    elif status == "clarification_required" and result.get("itinerary"):
        st.info(
            "식사 후보를 확정하기 전 관광 일정 초안을 먼저 생성했습니다. "
            "아래 선택지에서 검색 반경 확대 또는 식사 제외를 선택하면 "
            "현재 관광 조건을 유지한 채 최종 일정을 다시 검증합니다."
        )
        validation = result.get("validation") or {}
        if validation and not validation.get("valid"):
            st.warning(
                "현재 관광 일정은 식사 확정 전 초안이며 거리·시간 보정이 "
                "추가로 필요합니다."
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
        for item in conversation:
            with st.chat_message(item["role"]):
                st.markdown(str(item["content"]))


def _render_evaluation_results(artifact: Mapping[str, Any]) -> None:
    report = dict(artifact.get("report") or {})
    generation_usage = dict(artifact.get("generation_usage") or {})
    judge_usage = dict(artifact.get("judge_usage") or {})
    discarded_usage = dict(
        artifact.get("discarded_preexisting_usage") or {}
    )

    st.subheader("2. 평가 결과")
    status_label = "통과" if report.get("passed") else "기준 미달"
    if report.get("passed"):
        st.success(f"전체 평가: {status_label}")
    else:
        st.error(f"전체 평가: {status_label}")

    summary_columns = st.columns(5)
    summary_columns[0].metric(
        "통과율",
        f"{float(report.get('pass_rate') or 0):.1%}",
    )
    summary_columns[1].metric(
        "평균 점수",
        f"{float(report.get('average_score') or 0):.3f}",
    )
    summary_columns[2].metric("실행 케이스", int(report.get("case_count") or 0))
    summary_columns[3].metric(
        "RAG LLM 호출",
        int(generation_usage.get("calls") or 0),
    )
    summary_columns[4].metric(
        "전체 토큰",
        int(generation_usage.get("total_tokens") or 0)
        + int(judge_usage.get("total_tokens") or 0),
    )
    st.caption(
        "점수는 골든셋 기대값과 실제 결과를 비교한 0~1 값입니다. "
        "통과율은 개별 통과 기준을 넘은 케이스의 비율입니다."
    )
    if int(discarded_usage.get("calls") or 0):
        st.caption(
            "평가 시작 전 캐시된 RAG 사용량 "
            f"{int(discarded_usage.get('calls') or 0)}회는 합계에서 제외했습니다."
        )

    case_rows = []
    for case in report.get("cases") or []:
        case_rows.append(
            {
                "케이스": case.get("case_id"),
                "판정": "PASS" if case.get("passed") else "FAIL",
                "점수": float(case.get("score") or 0),
                "결과 상태": case.get("result_status"),
                "응답 시간(ms)": float(case.get("latency_ms") or 0),
                "실패 태그": ", ".join(case.get("failure_tags") or []),
            }
        )
    if case_rows:
        st.dataframe(
            pd.DataFrame(case_rows),
            use_container_width=True,
            hide_index=True,
        )

    chart_left, chart_right = st.columns(2)
    metric_averages = dict(report.get("metric_averages") or {})
    with chart_left:
        st.markdown("##### 지표별 평균")
        if metric_averages:
            metric_frame = pd.DataFrame(
                {
                    "지표": list(metric_averages),
                    "점수": [
                        float(value) for value in metric_averages.values()
                    ],
                }
            ).set_index("지표")
            st.bar_chart(metric_frame, horizontal=True)
        else:
            st.caption("표시할 지표가 없습니다.")

    failure_counts = dict(report.get("failure_counts") or {})
    with chart_right:
        st.markdown("##### 실패 원인")
        if failure_counts:
            failure_frame = pd.DataFrame(
                {
                    "실패 태그": list(failure_counts),
                    "건수": [
                        int(value) for value in failure_counts.values()
                    ],
                }
            ).set_index("실패 태그")
            st.bar_chart(failure_frame, horizontal=True)
        else:
            st.success("실패 태그가 없습니다.")

    with st.expander("케이스별 세부 채점"):
        for case in report.get("cases") or []:
            icon = "✅" if case.get("passed") else "❌"
            st.markdown(
                f"**{icon} {case.get('case_id')} — "
                f"{float(case.get('score') or 0):.3f}**"
            )
            metric_rows = [
                {
                    "지표": metric.get("name"),
                    "값": float(metric.get("value") or 0),
                    "기준": float(metric.get("threshold") or 0),
                    "통과": "예" if metric.get("passed") else "아니오",
                    "필수 게이트": "예" if metric.get("gate") else "아니오",
                }
                for metric in case.get("metrics") or []
            ]
            if metric_rows:
                st.dataframe(
                    pd.DataFrame(metric_rows),
                    use_container_width=True,
                    hide_index=True,
                )
            judge = case.get("judge")
            if judge:
                st.caption(
                    "LLM 심사: "
                    + ("통과" if judge.get("passed") else "실패")
                    + f" · 모델 {judge.get('model')}"
                )
                for reason in judge.get("reasons") or []:
                    st.write(f"- {reason}")
            st.divider()

    with st.expander("API 사용량"):
        usage_rows = []
        for source, summary in (
            ("RAG 생성", generation_usage),
            ("LLM 심사", judge_usage),
        ):
            usage_rows.append(
                {
                    "구분": source,
                    "호출": int(summary.get("calls") or 0),
                    "입력 토큰": int(summary.get("input_tokens") or 0),
                    "출력 토큰": int(summary.get("output_tokens") or 0),
                    "전체 토큰": int(summary.get("total_tokens") or 0),
                }
            )
        st.dataframe(
            pd.DataFrame(usage_rows),
            use_container_width=True,
            hide_index=True,
        )

    download_left, download_right = st.columns(2)
    export_payload = {
        key: value
        for key, value in artifact.items()
        if key != "markdown"
    }
    with download_left:
        st.download_button(
            "JSON 결과 다운로드",
            data=json.dumps(export_payload, ensure_ascii=False, indent=2),
            file_name="rag-evaluation-result.json",
            mime="application/json",
            use_container_width=True,
        )
    with download_right:
        st.download_button(
            "Markdown 보고서 다운로드",
            data=str(artifact.get("markdown") or ""),
            file_name="rag-evaluation-result.md",
            mime="text/markdown",
            use_container_width=True,
        )


def _run_answer_comparison(
    *,
    question: str,
    baseline_model: str,
    judge_model: str,
    repeat_count: int,
) -> dict[str, Any]:
    orchestrator = _rag()
    # `_rag()` is a cached resource shared with the schedule test page.
    # Exclude token records left by earlier interactions from this experiment.
    discarded_usage = _drain_usage(orchestrator)
    comparator = OpenAIResponseComparator(
        baseline_model=baseline_model.strip() or None,
        judge_model=judge_model.strip() or None,
    )
    comparison_values = []
    runs: list[dict[str, Any]] = []
    all_rag_usage: list[dict[str, Any]] = []
    all_baseline_usage: list[dict[str, Any]] = []
    all_judge_usage: list[dict[str, Any]] = []
    reusable_conditions: dict[str, Any] | None = None
    progress = st.progress(0, text="A/B 비교 평가를 준비하고 있습니다.")

    try:
        for run_index in range(1, repeat_count + 1):
            progress.progress(
                (run_index - 1) / repeat_count,
                text=f"{run_index}/{repeat_count}회: RAG 답변 생성 중",
            )
            started = time.perf_counter()
            condition_reused = run_index > 1 and reusable_conditions is not None
            rag_result = (
                orchestrator.run(selected_options=reusable_conditions)
                if condition_reused
                else orchestrator.run(message=question)
            )
            rag_latency_ms = (time.perf_counter() - started) * 1000
            run_rag_usage = _drain_usage(orchestrator)
            all_rag_usage.extend(run_rag_usage)
            if (
                reusable_conditions is None
                and rag_result.get("status") != "clarification_required"
                and isinstance(rag_result.get("conditions"), Mapping)
            ):
                reusable_conditions = dict(rag_result["conditions"])
            progress.progress(
                (run_index - 0.5) / repeat_count,
                text=f"{run_index}/{repeat_count}회: 기본 LLM 생성·익명 심사 중",
            )
            comparison = comparator.compare(
                question=question,
                rag_result=rag_result,
            )
            comparison_values.append(comparison)
            comparison_payload = comparison.to_dict()
            baseline_usage = dict(
                comparison_payload.get("usage", {}).get("baseline", {})
            )
            judge_usage = dict(
                comparison_payload.get("usage", {}).get("judge", {})
            )
            all_baseline_usage.append(
                {"stage": "baseline_answer", **baseline_usage}
            )
            all_judge_usage.append({"stage": "ab_judge", **judge_usage})
            runs.append(
                {
                    "run": run_index,
                    "comparison": comparison_payload,
                    "rag_status": rag_result.get("status"),
                    "rag_latency_ms": round(rag_latency_ms, 3),
                    "rag_usage": _usage_summary(run_rag_usage),
                    "condition_reused": condition_reused,
                }
            )
            progress.progress(
                run_index / repeat_count,
                text=f"A/B 비교 평가 {run_index}/{repeat_count}회 완료",
            )
    finally:
        progress.empty()
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "question": question,
        "repeat_count": repeat_count,
        "summary": summarize_answer_comparisons(comparison_values),
        "runs": runs,
        "total_usage": {
            "rag": _usage_summary(all_rag_usage),
            "baseline": _usage_summary(all_baseline_usage),
            "judge": _usage_summary(all_judge_usage),
        },
        "discarded_preexisting_usage": _usage_summary(discarded_usage),
    }


def _render_answer_comparison_results(
    artifact: Mapping[str, Any],
) -> None:
    summary_data = dict(artifact.get("summary") or {})
    runs = list(artifact.get("runs") or [])
    if not runs:
        st.error("표시할 반복 평가 결과가 없습니다.")
        return

    win_counts = dict(summary_data.get("win_counts") or {})
    st.subheader("반복 비교 결과")
    summary = st.columns(5)
    summary[0].metric(
        "평가 횟수",
        int(summary_data.get("run_count") or 0),
    )
    summary[1].metric(
        "기본 LLM 평균",
        f"{float(summary_data.get('baseline', {}).get('mean') or 0):.1f}점",
    )
    summary[2].metric(
        "RAG + LLM 평균",
        f"{float(summary_data.get('rag', {}).get('mean') or 0):.1f}점",
    )
    summary[3].metric(
        "평균 개선폭",
        f"{float(summary_data.get('average_improvement') or 0):+.1f}점",
    )
    summary[4].metric(
        "RAG 승리",
        f"{int(win_counts.get('rag') or 0)}회",
    )

    score_distribution_rows = []
    for label, key in (("기본 LLM", "baseline"), ("RAG + LLM", "rag")):
        values = dict(summary_data.get(key) or {})
        score_distribution_rows.append(
            {
                "답변": label,
                "평균": float(values.get("mean") or 0),
                "표준편차": float(values.get("stddev") or 0),
                "최소": float(values.get("minimum") or 0),
                "최대": float(values.get("maximum") or 0),
            }
        )
    st.dataframe(
        pd.DataFrame(score_distribution_rows),
        use_container_width=True,
        hide_index=True,
    )
    win_columns = st.columns(3)
    win_columns[0].metric("기본 LLM 승리", int(win_counts.get("baseline") or 0))
    win_columns[1].metric("RAG 승리", int(win_counts.get("rag") or 0))
    win_columns[2].metric("동점", int(win_counts.get("tie") or 0))

    criterion_labels = {
        "instruction_following": "조건·지시 준수",
        "answer_completeness": "답변 완성도",
        "relevance": "질문 관련성",
        "grounding": "근거성",
        "itinerary_feasibility": "일정 실행 가능성",
        "explanation_quality": "설명 품질",
    }
    criterion_averages = dict(
        summary_data.get("criterion_averages") or {}
    )
    average_rows = [
        {
            "평가 기준": criterion_labels.get(name, name),
            "기본 LLM": float(
                criterion_averages.get(name, {}).get("baseline") or 0
            ),
            "RAG + LLM": float(
                criterion_averages.get(name, {}).get("rag") or 0
            ),
        }
        for name in criterion_labels
    ]
    average_frame = pd.DataFrame(average_rows)
    st.markdown("##### 반복 전체 기준별 평균")
    st.dataframe(average_frame, use_container_width=True, hide_index=True)
    st.bar_chart(
        average_frame.set_index("평가 기준")[["기본 LLM", "RAG + LLM"]],
        horizontal=True,
    )

    run_rows = []
    for run in runs:
        run_comparison = dict(run.get("comparison") or {})
        run_rows.append(
            {
                "회차": int(run.get("run") or 0),
                "기본 LLM": float(
                    run_comparison.get("baseline", {}).get(
                        "overall_score"
                    )
                    or 0
                ),
                "RAG + LLM": float(
                    run_comparison.get("rag", {}).get("overall_score") or 0
                ),
                "승자": {
                    "baseline": "기본 LLM",
                    "rag": "RAG + LLM",
                    "tie": "동점",
                }.get(run_comparison.get("winner"), "판정 없음"),
                "RAG 상태": run.get("rag_status"),
                "RAG 응답시간(초)": round(
                    float(run.get("rag_latency_ms") or 0) / 1000,
                    3,
                ),
            }
        )
    st.markdown("##### 회차별 점수")
    run_frame = pd.DataFrame(run_rows)
    st.dataframe(run_frame, use_container_width=True, hide_index=True)
    st.line_chart(
        run_frame.set_index("회차")[["기본 LLM", "RAG + LLM"]]
    )

    selected_run_number = st.selectbox(
        "상세 답변을 확인할 회차",
        options=[int(run.get("run") or 0) for run in runs],
        index=len(runs) - 1,
    )
    selected_run = next(
        run
        for run in runs
        if int(run.get("run") or 0) == selected_run_number
    )
    comparison = dict(selected_run.get("comparison") or {})
    baseline = dict(comparison.get("baseline") or {})
    rag = dict(comparison.get("rag") or {})
    winner = comparison.get("winner")
    winner_label = {
        "rag": "RAG + LLM",
        "baseline": "기본 LLM",
        "tie": "동점",
    }.get(winner, "판정 없음")

    st.subheader(f"{selected_run_number}회차 상세 비교")
    if winner == "rag":
        st.success(f"우수 답변: {winner_label}")
    elif winner == "baseline":
        st.warning(f"우수 답변: {winner_label}")
    else:
        st.info(f"비교 판정: {winner_label}")

    detail_summary = st.columns(4)
    detail_summary[0].metric(
        "기본 LLM",
        f"{float(baseline.get('overall_score') or 0):.1f}점",
    )
    detail_summary[1].metric(
        "RAG + LLM",
        f"{float(rag.get('overall_score') or 0):.1f}점",
    )
    detail_summary[2].metric(
        "점수 차이",
        f"{float(comparison.get('score_difference') or 0):.1f}점",
    )
    detail_summary[3].metric(
        "RAG 결과 상태",
        str(selected_run.get("rag_status") or "unknown"),
    )

    baseline_scores = dict(baseline.get("scores") or {})
    rag_scores = dict(rag.get("scores") or {})
    score_rows = [
        {
            "평가 기준": criterion_labels.get(name, name),
            "기본 LLM": int(baseline_scores.get(name) or 0),
            "RAG + LLM": int(rag_scores.get(name) or 0),
            "RAG 개선폭": (
                int(rag_scores.get(name) or 0)
                - int(baseline_scores.get(name) or 0)
            ),
        }
        for name in criterion_labels
    ]
    score_frame = pd.DataFrame(score_rows)
    st.dataframe(score_frame, use_container_width=True, hide_index=True)
    st.bar_chart(
        score_frame.set_index("평가 기준")[["기본 LLM", "RAG + LLM"]],
        horizontal=True,
    )

    answer_left, answer_right = st.columns(2)
    with answer_left:
        st.markdown("##### 기본 LLM 답변")
        st.caption(
            f"모델: {comparison.get('baseline_model')} · 검색/DB 미사용"
        )
        st.text(str(baseline.get("answer") or ""))
    with answer_right:
        st.markdown("##### RAG + LLM 답변")
        st.caption(
            "AIHub 동선·TourAPI 검색·화이트리스트·운영시간/거리 검증 사용"
        )
        st.text(str(rag.get("answer") or ""))

    st.markdown("##### 평가 근거")
    for reason in comparison.get("rationale") or []:
        st.write(f"- {reason}")
    st.caption(
        "평가 모델에는 두 답변을 기본 LLM/RAG라는 이름 대신 A/B로 전달합니다. "
        "3점 미만의 차이는 동점으로 처리합니다."
    )

    total_usage = dict(artifact.get("total_usage") or {})
    rag_usage = dict(total_usage.get("rag") or {})
    baseline_usage = dict(total_usage.get("baseline") or {})
    judge_usage = dict(total_usage.get("judge") or {})
    discarded_usage = dict(
        artifact.get("discarded_preexisting_usage") or {}
    )
    with st.expander("응답 시간·API 사용량"):
        usage_rows = [
            {
                "구분": "RAG 파이프라인",
                "호출": int(rag_usage.get("calls") or 0),
                "입력 토큰": int(rag_usage.get("input_tokens") or 0),
                "출력 토큰": int(rag_usage.get("output_tokens") or 0),
                "전체 토큰": int(rag_usage.get("total_tokens") or 0),
            },
            {
                "구분": "기본 LLM 답변",
                "호출": int(baseline_usage.get("calls") or 0),
                "입력 토큰": int(baseline_usage.get("input_tokens") or 0),
                "출력 토큰": int(baseline_usage.get("output_tokens") or 0),
                "전체 토큰": int(baseline_usage.get("total_tokens") or 0),
            },
            {
                "구분": "익명 A/B 심사",
                "호출": int(judge_usage.get("calls") or 0),
                "입력 토큰": int(judge_usage.get("input_tokens") or 0),
                "출력 토큰": int(judge_usage.get("output_tokens") or 0),
                "전체 토큰": int(judge_usage.get("total_tokens") or 0),
            },
        ]
        st.metric(
            "선택 회차 RAG 응답 시간",
            f"{float(selected_run.get('rag_latency_ms') or 0) / 1000:.2f}초",
        )
        st.dataframe(
            pd.DataFrame(usage_rows),
            use_container_width=True,
            hide_index=True,
        )
        discarded_calls = int(discarded_usage.get("calls") or 0)
        if discarded_calls:
            st.info(
                "평가 시작 전에 캐시된 RAG 사용량 "
                f"{discarded_calls}회·"
                f"{int(discarded_usage.get('total_tokens') or 0):,}토큰을 "
                "이번 평가 합계에서 제외했습니다."
            )
        stage_labels = {
            "travel_condition_extraction": "조건 추출",
            "tourapi_itinerary_draft": "일정 생성",
            "repaired_tourapi_itinerary_draft": "일정 자동 수정",
        }
        stage_rows = []
        for stage, values in dict(rag_usage.get("by_stage") or {}).items():
            stage_rows.append(
                {
                    "RAG 단계": stage_labels.get(stage, stage),
                    "호출": int(values.get("calls") or 0),
                    "입력 토큰": int(values.get("input_tokens") or 0),
                    "출력 토큰": int(values.get("output_tokens") or 0),
                    "추론 토큰": int(values.get("reasoning_tokens") or 0),
                    "프롬프트 문자": int(
                        values.get("input_characters") or 0
                    ),
                }
            )
        if stage_rows:
            st.caption(
                "RAG 단계별 실제 사용량입니다. 입력 토큰에는 시스템 프롬프트, "
                "JSON Schema, 검색 후보 컨텍스트가 포함됩니다."
            )
            st.dataframe(
                pd.DataFrame(stage_rows),
                use_container_width=True,
                hide_index=True,
            )

    st.download_button(
        "A/B 비교 결과 JSON 다운로드",
        data=json.dumps(dict(artifact), ensure_ascii=False, indent=2),
        file_name="llm-vs-rag-comparison.json",
        mime="application/json",
        use_container_width=True,
    )


def _render_answer_comparison_page() -> None:
    st.subheader("임의 질문으로 LLM 대 RAG 비교")
    st.write(
        "같은 질문을 검색 없는 기본 LLM과 현재 RAG에 각각 전달한 뒤, "
        "두 답변을 익명 A/B 방식으로 평가합니다."
    )
    st.markdown("#### 평가 기준")
    st.markdown(
        """
두 답변은 어느 쪽이 RAG인지 공개하지 않은 상태에서 동일한 기준으로
평가합니다. 사용자의 조건과 요청 형식을 지켰는지, 요청한 일정이 실제로
완성되었는지, 질문과 관련된 내용인지, 장소 ID·출처·검증 결과처럼 확인할 수
있는 근거가 있는지, 시간과 이동을 고려해 실행 가능한지, 장소 설명과 선택
이유가 이해하기 쉬운지를 종합해 점수를 계산합니다. 식사 일정은 관광지 개수와
구분하며, 단순히 재질문만 하고 요청한 일정을 제시하지 않은 답변은 완성된
답변으로 평가하지 않습니다.
"""
    )
    st.caption(
        "조건·지시 준수 20% · 답변 완성도 20% · 질문 관련성 10% · "
        "근거성 20% · 일정 실행 가능성 20% · 설명 품질 10%로 계산하며, "
        "점수 차이가 3점 미만이면 동점입니다."
    )
    st.warning(
        "한 번 실행하면 RAG 생성 호출, 기본 LLM 호출, A/B 심사 호출이 "
        "발생합니다. 질문에 필수 조건이 부족하면 RAG의 재질문 능력을 "
        "평가하게 됩니다."
    )
    sample_labels = [*COMPARISON_QUESTION_SAMPLES, "직접 입력"]
    selected_sample = st.selectbox(
        "샘플 질문 선택",
        options=sample_labels,
        help="20개 샘플 중 하나를 선택한 뒤 질문 내용을 자유롭게 수정할 수 있습니다.",
    )
    sample_index = sample_labels.index(selected_sample)
    sample_question = COMPARISON_QUESTION_SAMPLES.get(selected_sample, "")
    with st.form("answer_comparison_form"):
        question = st.text_area(
            "비교할 임의 질문",
            value=sample_question,
            height=130,
            key=f"comparison_question_{sample_index}",
        )
        model_left, model_right = st.columns(2)
        with model_left:
            baseline_model = st.text_input(
                "기본 LLM 모델",
                value=os.getenv("OPENAI_CHAT_MODEL", "gpt-5-mini"),
            )
        with model_right:
            judge_model = st.text_input(
                "A/B 평가 모델",
                value=os.getenv(
                    "OPENAI_EVAL_JUDGE_MODEL",
                    "gpt-5-mini",
                ),
            )
        repeat_count = st.number_input(
            "평가 횟수",
            min_value=1,
            max_value=120,
            value=1,
            step=1,
            help=(
                "동일 질문으로 RAG 생성, 기본 LLM 생성, 익명 A/B 심사를 "
                "지정 횟수만큼 반복합니다."
            ),
        )
        large_run_confirmed = st.checkbox(
            "10회를 초과하는 대량 API 실행의 시간과 비용을 확인했습니다.",
            value=False,
        )
        st.caption(
            "1회당 기본 LLM 1회와 A/B 심사 1회가 고정으로 호출되며, "
            "RAG 내부에서는 조건 추출·일정 생성·자동 수정 호출이 추가될 수 "
            "있습니다."
        )
        submitted = st.form_submit_button(
            "두 답변 생성 후 비교 평가",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        st.session_state.comparison_artifact = None
        if not question.strip():
            st.session_state.comparison_error = "질문을 입력하세요."
        elif int(repeat_count) > 10 and not large_run_confirmed:
            st.session_state.comparison_error = (
                "10회를 초과하려면 대량 API 실행 확인 항목을 선택하세요."
            )
        else:
            try:
                st.session_state.comparison_artifact = _run_answer_comparison(
                    question=question.strip(),
                    baseline_model=baseline_model,
                    judge_model=judge_model,
                    repeat_count=int(repeat_count),
                )
                st.session_state.comparison_error = None
            except Exception as exc:
                st.session_state.comparison_error = (
                    f"{type(exc).__name__}: {exc}"
                )

    if st.session_state.comparison_error:
        st.error(st.session_state.comparison_error)
    if st.session_state.comparison_artifact:
        _render_answer_comparison_results(
            st.session_state.comparison_artifact
        )


def _render_golden_evaluation_page() -> None:
    st.subheader("골든셋 회귀 평가")
    st.info(
        "기본 평가는 코드 규칙으로 재현 가능하게 채점합니다. "
        "‘LLM 심사’를 켜면 설명 품질·지시 준수·동선 자연스러움을 "
        "추가로 심사하지만 OpenAI API 비용이 더 발생합니다."
    )

    if not EVAL_DATASET.exists():
        st.error(f"평가 데이터셋을 찾을 수 없습니다: {EVAL_DATASET}")
        return

    cases = _evaluation_cases(str(EVAL_DATASET))
    case_by_id = {case.case_id: case for case in cases}
    labels = {
        case.case_id: (
            f"{case.case_id} · "
            f"{'조건 추출' if case.stage == 'conditions' else '전체 RAG'}"
        )
        for case in cases
    }

    st.subheader("1. 실행 설정")
    with st.form("rag_evaluation_form"):
        selected_case_ids = st.multiselect(
            "평가 케이스",
            options=list(case_by_id),
            default=[cases[0].case_id],
            format_func=lambda value: labels[value],
            help=(
                "조건 추출 케이스는 프롬프트의 구조화 정확도를, "
                "전체 RAG 케이스는 검색·일정·검증까지 측정합니다."
            ),
        )
        settings_left, settings_right = st.columns(2)
        with settings_left:
            repeat = st.number_input(
                "반복 횟수",
                min_value=1,
                max_value=10,
                value=1,
                help="같은 입력의 안정성과 변동성을 확인할 때 늘립니다.",
            )
            case_score = st.slider(
                "개별 케이스 통과 점수",
                min_value=0.0,
                max_value=1.0,
                value=0.80,
                step=0.05,
            )
        with settings_right:
            pass_rate = st.slider(
                "전체 통과율 기준",
                min_value=0.0,
                max_value=1.0,
                value=0.80,
                step=0.05,
            )
            llm_judge = st.checkbox(
                "LLM 심사 추가",
                value=False,
                help="결정론적 지표에 OpenAI의 정성 pass/fail 심사를 더합니다.",
            )
            judge_model = st.text_input(
                "심사 모델",
                value=os.getenv(
                    "OPENAI_EVAL_JUDGE_MODEL",
                    os.getenv("OPENAI_CHAT_MODEL", "gpt-5-mini"),
                ),
                disabled=not llm_judge,
            )
        run_submitted = st.form_submit_button(
            "선택한 평가 실행",
            type="primary",
            use_container_width=True,
        )

    if run_submitted:
        st.session_state.evaluation_artifact = None
        if not selected_case_ids:
            st.session_state.evaluation_error = (
                "평가할 케이스를 하나 이상 선택하세요."
            )
        else:
            selected_cases = [
                case_by_id[case_id] for case_id in selected_case_ids
            ]
            try:
                st.session_state.evaluation_artifact = (
                    _run_selected_evaluation(
                        cases=selected_cases,
                        repeat=int(repeat),
                        case_score=float(case_score),
                        pass_rate=float(pass_rate),
                        llm_judge=bool(llm_judge),
                        judge_model=judge_model,
                    )
                )
                st.session_state.evaluation_error = None
            except Exception as exc:
                st.session_state.evaluation_error = (
                    f"{type(exc).__name__}: {exc}"
                )

    if st.session_state.evaluation_error:
        st.error(st.session_state.evaluation_error)
    if st.session_state.evaluation_artifact:
        _render_evaluation_results(st.session_state.evaluation_artifact)


def _render_evaluation_page() -> None:
    st.title("📊 RAG 평가 엔진")
    st.caption(
        "고정된 골든셋 회귀 평가와 임의 질문 기반 LLM 대 RAG A/B 비교를 "
        "한 화면에서 실행합니다."
    )
    golden_tab, comparison_tab = st.tabs(
        ["골든셋 자동 평가", "임의 질문 A/B 비교"]
    )
    with golden_tab:
        _render_golden_evaluation_page()
    with comparison_tab:
        _render_answer_comparison_page()


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

    with st.sidebar:
        st.markdown("### 화면 선택")
        selected_menu = st.radio(
            "메뉴",
            [MENU_RAG_TEST, MENU_EVALUATION],
            label_visibility="collapsed",
        )
        st.markdown("### 테스트 제어")
        if selected_menu == MENU_RAG_TEST:
            if st.button("일정 결과 초기화", use_container_width=True):
                st.session_state.rag_result = None
                st.session_state.guided_dialogue = None
                st.session_state.conversation = []
                st.session_state.last_error = None
                st.rerun()
        elif st.button("평가 결과 초기화", use_container_width=True):
            st.session_state.evaluation_artifact = None
            st.session_state.evaluation_error = None
            st.session_state.comparison_artifact = None
            st.session_state.comparison_error = None
            st.rerun()
        st.info(
            "테스트가 끝나면 `rag_test_frontend` 폴더만 삭제하면 됩니다."
        )

    if selected_menu == MENU_EVALUATION:
        _render_evaluation_page()
        return

    st.title("🧪 제주 여행 RAG 임시 테스트")
    st.caption(
        "src/rag의 순수 Python 인터페이스를 직접 호출합니다. "
        "backend에는 연결하지 않습니다."
    )

    if st.session_state.last_error:
        st.error(st.session_state.last_error)

    result = st.session_state.rag_result
    if not result:
        _render_guided_intake()
        prompt = st.chat_input("답변을 입력하거나 위 선택지를 눌러주세요.")
        if prompt:
            _submit_guided_value(prompt)
            st.rerun()
    else:
        _render_conversation()
        _render_summary(result)
        _render_clarification(result)
        _render_itinerary(result)
        _render_diagnostics(result)

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
