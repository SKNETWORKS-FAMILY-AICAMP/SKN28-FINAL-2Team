"""Deterministic dialogue state for the four-step initial itinerary intake."""

from __future__ import annotations

import re
from typing import Any, Mapping

from .conditions import (
    GUIDED_TRAVEL_STYLE_ALIASES,
    GUIDED_TRAVEL_STYLE_PROFILES,
)


GUIDED_DIALOGUE_STEPS = (
    {
        "field": "duration_days",
        "question": "제주 여행은 총 며칠 동안 진행하시나요?",
        "options": tuple(
            {"label": f"{day}일", "value": str(day)}
            for day in range(1, 6)
        ),
    },
    {
        "field": "party_size",
        "question": "이번 여행은 총 몇 명이 함께하나요?",
        "options": tuple(
            {"label": f"{count}명", "value": str(count)}
            for count in range(1, 7)
        ),
    },
    {
        "field": "local_transport",
        "question": "제주에서는 어떤 교통수단으로 이동하시나요?",
        "options": (
            {"label": "렌터카", "value": "rental_car"},
            {"label": "자가용", "value": "own_car"},
            {"label": "대중교통", "value": "public_transit"},
            {"label": "택시", "value": "taxi"},
            {"label": "혼합", "value": "mixed"},
        ),
    },
    {
        "field": "travel_style",
        "question": "어떤 스타일의 제주 여행을 원하시나요?",
        "options": (
            {"label": "힐링·여유", "value": "healing"},
            {"label": "자연·풍경", "value": "nature"},
            {"label": "역사·문화", "value": "culture"},
            {"label": "체험·액티비티", "value": "activity"},
            {"label": "시장·로컬", "value": "local"},
            {"label": "인기 명소 중심", "value": "popular"},
        ),
    },
)

TRANSPORT_ALIASES = {
    "렌터카": "rental_car",
    "렌트카": "rental_car",
    "자가용": "own_car",
    "자차": "own_car",
    "대중교통": "public_transit",
    "버스": "public_transit",
    "택시": "taxi",
    "혼합": "mixed",
    "여러 교통수단": "mixed",
}


def start_guided_dialogue() -> dict[str, Any]:
    """Start the initial itinerary conversation at the duration question."""

    return _dialogue_payload(step_index=0, answers={})


def submit_guided_answer(
    state: Mapping[str, Any] | None,
    answer: Any,
) -> dict[str, Any]:
    """Validate one answer and advance to the next guided question."""

    current = dict(state or start_guided_dialogue())
    answers = dict(current.get("answers") or {})
    step_index = int(current.get("step_index") or 0)
    if step_index >= len(GUIDED_DIALOGUE_STEPS):
        return _ready_payload(answers)

    step = GUIDED_DIALOGUE_STEPS[step_index]
    field = str(step["field"])
    try:
        answers[field] = _parse_answer(field, answer)
    except ValueError as exc:
        return {
            **_dialogue_payload(step_index=step_index, answers=answers),
            "error": str(exc),
        }

    next_index = step_index + 1
    if next_index >= len(GUIDED_DIALOGUE_STEPS):
        return _ready_payload(answers)
    return _dialogue_payload(step_index=next_index, answers=answers)


def _dialogue_payload(
    *,
    step_index: int,
    answers: Mapping[str, Any],
) -> dict[str, Any]:
    step = GUIDED_DIALOGUE_STEPS[step_index]
    return {
        "status": "collecting_conditions",
        "ready": False,
        "step_index": step_index,
        "field": step["field"],
        "question": step["question"],
        "options": [dict(option) for option in step["options"]],
        "answers": dict(answers),
    }


def _ready_payload(answers: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "duration_days",
        "party_size",
        "local_transport",
        "travel_style",
    }
    missing = sorted(required - set(answers))
    if missing:
        raise ValueError(
            "guided dialogue is missing fields: " + ", ".join(missing)
        )
    return {
        "status": "ready_to_generate",
        "ready": True,
        "step_index": len(GUIDED_DIALOGUE_STEPS),
        "field": None,
        "question": None,
        "options": [],
        "answers": dict(answers),
        "generation_inputs": {
            "duration_days": int(answers["duration_days"]),
            "party_size": int(answers["party_size"]),
            "local_transport": str(answers["local_transport"]),
            "travel_style": str(answers["travel_style"]),
        },
    }


def _parse_answer(field: str, answer: Any) -> Any:
    text = str(answer).strip()
    if not text:
        raise ValueError("답변을 입력하거나 선택해 주세요.")
    if field in {"duration_days", "party_size"}:
        match = re.search(r"\d+", text)
        if match is None:
            label = "여행 일수" if field == "duration_days" else "여행 인원"
            raise ValueError(f"{label}를 숫자로 입력해 주세요.")
        value = int(match.group())
        if not 1 <= value <= 30:
            raise ValueError("1에서 30 사이의 값을 입력해 주세요.")
        return value
    if field == "local_transport":
        canonical = TRANSPORT_ALIASES.get(text, text)
        allowed = {
            str(option["value"])
            for option in GUIDED_DIALOGUE_STEPS[2]["options"]
        }
        if canonical not in allowed:
            raise ValueError(
                "렌터카, 자가용, 대중교통, 택시 또는 혼합 중에서 선택해 주세요."
            )
        return canonical
    if field == "travel_style":
        canonical = GUIDED_TRAVEL_STYLE_ALIASES.get(text, text)
        if canonical not in GUIDED_TRAVEL_STYLE_PROFILES:
            raise ValueError("화면에 표시된 여행 스타일 중 하나를 선택해 주세요.")
        return canonical
    raise ValueError(f"unsupported guided field: {field}")
