"""A/B evaluation for a plain LLM answer and the itinerary RAG answer."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
import re
from statistics import mean, pstdev
from typing import Any, Mapping, Sequence

from .llm import LLMError
from .langsmith_observability import maybe_wrap_openai_client
from .openai_responses import (
    configured_token_budgets,
    create_text_response,
    summed_usage,
)


COMPARISON_CRITERIA = (
    "instruction_following",
    "answer_completeness",
    "relevance",
    "grounding",
    "itinerary_feasibility",
    "explanation_quality",
)

COMPARISON_WEIGHTS = {
    "instruction_following": 0.20,
    "answer_completeness": 0.20,
    "relevance": 0.10,
    "grounding": 0.20,
    "itinerary_feasibility": 0.20,
    "explanation_quality": 0.10,
}

BASELINE_SYSTEM_PROMPT = """
당신은 제주 여행 일정 상담 LLM이다.
사용자 질문에 직접 답하되 검색, 데이터베이스, RAG, 지도 경로 API를 사용하지
않는다. 질문에 정보가 부족하면 임의로 확정하지 말고 필요한 내용을 질문한다.
현재 운영시간·요금·도로 이동시간을 확인한 것처럼 말하지 않는다. 일정 요청이면
날짜별 시간, 장소, 간단한 설명과 선택 이유를 읽기 쉽게 제시한다.
""".strip()

COMPARISON_JUDGE_PROMPT = """
당신은 두 여행 일정 답변을 익명으로 비교하는 엄격한 평가자다.
두 답변 중 어느 것이 RAG 답변인지 추측하지 말고 제공된 텍스트만 평가한다.

각 답변을 다음 기준으로 0~100점으로 채점한다.
1. instruction_following: 사용자의 명시 조건과 요청 형식을 지켰는가
2. answer_completeness: 요청한 날짜 수와 관광지 수를 실제 답변으로 완성했는가.
   나중에 답하겠다는 약속이나 재질문만 있는 답변은 완성된 답변이 아니다.
3. relevance: 질문과 관계없는 내용 없이 필요한 답을 했는가
4. grounding: 장소 ID, 출처, 검증 상태 등 확인 가능한 근거가 있으며 확인되지
   않은 운영시간·거리·요금을 사실처럼 단정하지 않았는가
5. itinerary_feasibility: 시간 순서, 이동, 운영시간, 필수·제외 조건을 고려한
   실행 가능한 일정인가
6. explanation_quality: 장소 설명과 선택 이유가 간결하고 이해하기 쉬운가

평가자가 외부 사실을 알고 있다고 가정하지 않는다. 답변 안에 제시된 근거와
검증 상태만으로 판단한다. 답변 길이 자체에는 가산점을 주지 않는다.
입력의 evaluation_facts는 코드로 계산한 권위 있는 사실이다.

강제 채점 규칙:
- 일정 생성 요청에 실제 일정이 0건이고 재질문·향후 답변 약속만 있으면
  instruction_following은 최대 20점, answer_completeness와
  itinerary_feasibility는 0점이다.
- required_conditions_complete가 true이면 추가 질문을 했다는 이유만으로
  가산점을 주지 않는다.
- 관광지 개수는 tourism_items만 센다. meal_items는 관광지 개수에서 제외하며,
  식사가 별도로 포함됐다는 이유로 "하루 관광지 3곳 초과"라고 감점하지 않는다.
- 코드가 valid=true라고 제공한 경우 외부 지식으로 검증 실패를 추정하지 않는다.
- 실제 장소 설명이 없는 답변에는 explanation_quality 고득점을 주지 않는다.

중요 출력 규칙:
- rationale의 모든 문장은 반드시 자연스러운 한국어로 작성한다.
- 영어 평가 문장이나 "Answer A/B" 같은 영어 머리말을 사용하지 않는다.
- 각 근거는 "답변 A는 …", "답변 B는 …", "종합하면 …"처럼 한국어로 쓴다.
- 점수 필드명은 스키마에 지정된 영문 키를 그대로 유지한다.
""".strip()

KOREAN_RATIONALE_PROMPT = """
입력된 A/B 평가 JSON의 점수는 절대 변경하지 말고, rationale만 자연스러운
한국어 평가 근거로 다시 작성한다. 영어 문장을 남기지 않는다. 답변은 제공된
JSON 스키마만 따른다.
""".strip()

COMPARISON_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answer_a", "answer_b", "rationale"],
    "properties": {
        "answer_a": {
            "type": "object",
            "additionalProperties": False,
            "required": list(COMPARISON_CRITERIA),
            "properties": {
                name: {"type": "integer", "minimum": 0, "maximum": 100}
                for name in COMPARISON_CRITERIA
            },
        },
        "answer_b": {
            "type": "object",
            "additionalProperties": False,
            "required": list(COMPARISON_CRITERIA),
            "properties": {
                name: {"type": "integer", "minimum": 0, "maximum": 100}
                for name in COMPARISON_CRITERIA
            },
        },
        "rationale": {
            "type": "array",
            "minItems": 1,
            "maxItems": 5,
            "items": {
                "type": "string",
                "description": "반드시 자연스러운 한국어로 작성한 평가 근거",
            },
        },
    },
}

KOREAN_RATIONALE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["rationale"],
    "properties": {
        "rationale": {
            "type": "array",
            "minItems": 1,
            "maxItems": 5,
            "items": {
                "type": "string",
                "description": "영어 없이 자연스러운 한국어로 쓴 평가 근거",
            },
        }
    },
}


@dataclass(frozen=True)
class ComparedAnswer:
    label: str
    answer: str
    scores: Mapping[str, int]
    overall_score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AnswerComparison:
    question: str
    baseline: ComparedAnswer
    rag: ComparedAnswer
    winner: str
    score_difference: float
    rationale: tuple[str, ...]
    baseline_model: str
    judge_model: str
    usage: Mapping[str, Mapping[str, int]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "baseline": self.baseline.to_dict(),
            "rag": self.rag.to_dict(),
            "winner": self.winner,
            "score_difference": self.score_difference,
            "rationale": list(self.rationale),
            "baseline_model": self.baseline_model,
            "judge_model": self.judge_model,
            "usage": {
                key: dict(value) for key, value in self.usage.items()
            },
        }


def summarize_answer_comparisons(
    comparisons: Sequence[AnswerComparison],
) -> dict[str, Any]:
    """Aggregate repeated A/B runs without discarding run-level results."""

    if not comparisons:
        raise ValueError("at least one answer comparison is required")

    baseline_scores = [
        value.baseline.overall_score for value in comparisons
    ]
    rag_scores = [value.rag.overall_score for value in comparisons]
    win_counts = {"baseline": 0, "rag": 0, "tie": 0}
    for value in comparisons:
        win_counts[value.winner] = win_counts.get(value.winner, 0) + 1

    criterion_averages: dict[str, dict[str, float]] = {}
    for criterion in COMPARISON_CRITERIA:
        criterion_averages[criterion] = {
            "baseline": round(
                mean(
                    float(value.baseline.scores[criterion])
                    for value in comparisons
                ),
                3,
            ),
            "rag": round(
                mean(
                    float(value.rag.scores[criterion])
                    for value in comparisons
                ),
                3,
            ),
        }

    def describe(values: Sequence[float]) -> dict[str, float]:
        return {
            "mean": round(mean(values), 3),
            "stddev": round(pstdev(values), 3),
            "minimum": round(min(values), 3),
            "maximum": round(max(values), 3),
        }

    return {
        "run_count": len(comparisons),
        "baseline": describe(baseline_scores),
        "rag": describe(rag_scores),
        "average_improvement": round(
            mean(
                value.rag.overall_score - value.baseline.overall_score
                for value in comparisons
            ),
            3,
        ),
        "win_counts": win_counts,
        "criterion_averages": criterion_averages,
    }


def _usage(response: Any) -> dict[str, int]:
    value = getattr(response, "usage", None)
    return {
        "input_tokens": int(getattr(value, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(value, "output_tokens", 0) or 0),
        "total_tokens": int(getattr(value, "total_tokens", 0) or 0),
    }


def _weighted_score(scores: Mapping[str, Any]) -> float:
    return round(
        sum(
            max(0, min(100, int(scores.get(name) or 0)))
            * COMPARISON_WEIGHTS[name]
            for name in COMPARISON_CRITERIA
        ),
        2,
    )


def _has_korean_rationale(items: Any) -> bool:
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        return False
    values = [str(item).strip() for item in items if str(item).strip()]
    return bool(values) and all(
        any("\uac00" <= char <= "\ud7a3" for char in value)
        for value in values
    )


def _requested_day_count(question: str) -> int | None:
    nights_days = re.search(r"(\d+)\s*박\s*(\d+)\s*일", question)
    if nights_days:
        return int(nights_days.group(2))
    days = re.search(r"(\d+)\s*일(?:간|짜리|\s*여행|\s*일정)", question)
    return int(days.group(1)) if days else None


def _requested_places_per_day(question: str) -> int | None:
    match = re.search(r"하루(?:에)?\s*(\d+)\s*곳", question)
    return int(match.group(1)) if match else None


def _is_itinerary_request(question: str) -> bool:
    return any(
        keyword in question
        for keyword in ("일정", "코스", "추천", "짜주세요", "계획")
    )


def _baseline_facts(answer: str) -> dict[str, Any]:
    time_entries = len(re.findall(r"\b\d{1,2}:\d{2}\b", answer))
    day_entries = len(
        re.findall(r"(?:Day\s*\d+|\d+\s*일차)", answer, flags=re.IGNORECASE)
    )
    future_promise = any(
        phrase in answer
        for phrase in (
            "알려주세요",
            "주시면",
            "제안드릴게요",
            "추천안 먼저",
            "어떤 쪽으로 할까요",
        )
    )
    actual_schedule_items = max(time_entries, day_entries)
    return {
        "actual_schedule_items": actual_schedule_items,
        "tourism_items": actual_schedule_items,
        "meal_items": 0,
        "clarification_only": future_promise and actual_schedule_items == 0,
        "has_descriptions": actual_schedule_items > 0,
    }


def _rag_facts(result: Mapping[str, Any]) -> dict[str, Any]:
    itinerary = result.get("itinerary")
    items = (
        list(itinerary)
        if isinstance(itinerary, Sequence)
        and not isinstance(itinerary, (str, bytes))
        else []
    )
    tourism_counts: dict[int, int] = {}
    tourism_items = 0
    meal_items = 0
    description_count = 0
    for item in items:
        if not isinstance(item, Mapping):
            continue
        is_meal = bool(item.get("meal_type")) or item.get("slot_kind") == "meal"
        if is_meal:
            meal_items += 1
        else:
            tourism_items += 1
            day = int(item.get("day") or 0)
            tourism_counts[day] = tourism_counts.get(day, 0) + 1
        if str(item.get("description") or "").strip():
            description_count += 1
    validation = result.get("validation")
    valid = (
        bool(validation.get("valid"))
        if isinstance(validation, Mapping)
        else None
    )
    return {
        "actual_schedule_items": tourism_items + meal_items,
        "tourism_items": tourism_items,
        "meal_items": meal_items,
        "tourism_items_by_day": tourism_counts,
        "clarification_only": not items and bool(
            result.get("clarification_questions")
        ),
        "has_descriptions": description_count > 0,
        "validation_valid": valid,
    }


def _required_conditions_complete(result: Mapping[str, Any]) -> bool:
    conditions = result.get("conditions")
    if not isinstance(conditions, Mapping):
        return False
    return bool(
        conditions.get("duration_days")
        and conditions.get("party_type")
        and conditions.get("local_transport")
        and conditions.get("preferred_visit_types")
    )


def _apply_score_guardrails(
    scores: Mapping[str, Any],
    *,
    facts: Mapping[str, Any],
    request_facts: Mapping[str, Any],
    answer_label: str,
) -> tuple[dict[str, int], list[str]]:
    adjusted = {
        name: max(0, min(100, int(scores.get(name) or 0)))
        for name in COMPARISON_CRITERIA
    }
    notes: list[str] = []
    if not request_facts.get("itinerary_requested"):
        return adjusted, notes

    actual = int(facts.get("tourism_items") or 0)
    expected = int(request_facts.get("expected_tourism_items") or 0)
    if expected > 0:
        completion = round(min(1.0, actual / expected) * 100)
        adjusted["answer_completeness"] = completion

    if bool(facts.get("clarification_only")) or actual == 0:
        adjusted["instruction_following"] = min(
            adjusted["instruction_following"],
            20,
        )
        adjusted["answer_completeness"] = 0
        adjusted["itinerary_feasibility"] = 0
        if not facts.get("has_descriptions"):
            adjusted["explanation_quality"] = min(
                adjusted["explanation_quality"],
                20,
            )
        notes.append(
            f"코드 검증: {answer_label}은 일정 생성 요청에 실제 관광지 일정을 "
            "제시하지 않고 재질문 또는 향후 답변 약속만 하여 완성도·지시 준수·"
            "일정 실행 가능성을 강제 감점했습니다."
        )
    elif expected > 0 and actual < expected:
        adjusted["instruction_following"] = min(
            adjusted["instruction_following"],
            adjusted["answer_completeness"],
        )
        notes.append(
            f"코드 검증: {answer_label}의 관광지는 요청된 {expected}곳 중 "
            f"{actual}곳만 확인되어 완성도 비율을 반영했습니다."
        )

    meals = int(facts.get("meal_items") or 0)
    if meals:
        notes.append(
            f"코드 검증: {answer_label}은 관광지 {actual}곳과 식사 {meals}건으로 "
            "구성되어 있으며 식사는 관광지 개수에서 제외했습니다."
        )
    return adjusted, notes


def format_rag_answer(result: Mapping[str, Any]) -> str:
    """Convert the structured RAG contract into a judge-readable answer."""

    status = str(result.get("status") or "unknown")
    lines = [
        f"상태: {status}",
        f"안내: {str(result.get('message') or '').strip()}",
    ]
    questions = result.get("clarification_questions")
    if isinstance(questions, Sequence) and not isinstance(
        questions,
        (str, bytes),
    ):
        for question in questions:
            lines.append(f"추가 질문: {question}")

    itinerary = result.get("itinerary")
    if isinstance(itinerary, Sequence) and not isinstance(
        itinerary,
        (str, bytes),
    ):
        facts = _rag_facts(result)
        lines.append(
            "일정 구성 요약: "
            f"관광지 {facts['tourism_items']}곳, 식사 {facts['meal_items']}건 "
            "(식사는 관광지 개수에서 제외)"
        )
        for item in itinerary:
            if not isinstance(item, Mapping):
                continue
            day = item.get("day")
            start = item.get("start_time") or ""
            end = item.get("end_time") or ""
            title = item.get("title") or item.get("place_name") or ""
            content_id = item.get("content_id")
            source = item.get("source") or "unknown"
            meal_type = str(item.get("meal_type") or "").strip()
            slot_kind = str(item.get("slot_kind") or "tourism").strip()
            item_type = (
                {"breakfast": "아침", "lunch": "점심", "dinner": "저녁"}.get(
                    meal_type,
                    "식사",
                )
                if meal_type or slot_kind == "meal"
                else "관광지"
            )
            lines.append(
                f"Day {day} | [{item_type}] | {start}~{end} | {title} "
                f"| TourAPI ID {content_id} | 출처 {source}"
            )
            description = str(item.get("description") or "").strip()
            reason = str(
                item.get("selection_reason") or item.get("reason") or ""
            ).strip()
            if description:
                lines.append(f"  설명: {description[:240]}")
            if reason:
                lines.append(f"  선택 이유: {reason[:240]}")

    validation = result.get("validation")
    if isinstance(validation, Mapping):
        compact_issues = []
        for issue in list(validation.get("issues") or [])[:10]:
            if not isinstance(issue, Mapping):
                continue
            compact_issues.append(
                {
                    key: issue.get(key)
                    for key in (
                        "code",
                        "day",
                        "slot_sequence",
                        "content_id",
                    )
                }
                | {"message": str(issue.get("message") or "")[:180]}
            )
        lines.append(
            "검증: "
            f"valid={bool(validation.get('valid'))}, "
            f"issues={json.dumps(compact_issues, ensure_ascii=False)}"
        )
    if not any(line.startswith("Day ") for line in lines):
        lines.append("생성된 일정 없음")
    return "\n".join(lines)


class OpenAIResponseComparator:
    """Generate the no-RAG baseline and anonymously score both answers."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        baseline_model: str | None = None,
        judge_model: str | None = None,
        timeout: float = 60.0,
        client: Any | None = None,
    ) -> None:
        self.baseline_model = (
            baseline_model
            or os.getenv("OPENAI_CHAT_MODEL")
            or "gpt-5-mini"
        )
        self.judge_model = (
            judge_model
            or os.getenv("OPENAI_EVAL_JUDGE_MODEL")
            or "gpt-5-mini"
        )
        if client is None:
            key = api_key or os.getenv("OPENAI_API_KEY", "")
            if not key:
                raise LLMError("OPENAI_API_KEY is not configured")
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise LLMError(
                    "openai is not installed; run: pip install -r requirements.txt"
                ) from exc
            client = OpenAI(api_key=key, timeout=timeout)
        self._client = maybe_wrap_openai_client(client)

    def compare(
        self,
        *,
        question: str,
        rag_result: Mapping[str, Any],
    ) -> AnswerComparison:
        prompt = question.strip()
        if not prompt:
            raise ValueError("comparison question must not be empty")

        baseline_answer, baseline_responses = create_text_response(
            client=self._client,
            label="OpenAI baseline",
            request={
                "model": self.baseline_model,
                "input": [
                    {"role": "system", "content": BASELINE_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            },
            token_budgets=configured_token_budgets(
                2200,
                3600,
                retry_env="RAG_EVAL_EMPTY_RESPONSE_RETRIES",
            ),
            evaluation=True,
        )

        rag_answer = format_rag_answer(rag_result)
        requested_days = _requested_day_count(prompt)
        requested_places = _requested_places_per_day(prompt)
        expected_tourism_items = (
            requested_days * requested_places
            if requested_days and requested_places
            else 0
        )
        baseline_facts = _baseline_facts(baseline_answer)
        rag_facts = _rag_facts(rag_result)
        request_facts = {
            "itinerary_requested": _is_itinerary_request(prompt),
            "requested_days": requested_days,
            "requested_tourism_places_per_day": requested_places,
            "expected_tourism_items": expected_tourism_items,
            "required_conditions_complete": _required_conditions_complete(
                rag_result
            ),
        }
        judge_payload = {
            "question": prompt,
            "answer_a": baseline_answer,
            "answer_b": rag_answer,
            "evaluation_facts": {
                "request": request_facts,
                "answer_a": baseline_facts,
                "answer_b": rag_facts,
            },
        }
        judge_text, judge_responses = create_text_response(
            client=self._client,
            label="OpenAI comparison judge",
            request={
                "model": self.judge_model,
                "input": [
                    {"role": "system", "content": COMPARISON_JUDGE_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(
                            judge_payload,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    },
                ],
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "llm_rag_answer_comparison",
                        "schema": COMPARISON_OUTPUT_SCHEMA,
                        "strict": True,
                    }
                },
            },
            token_budgets=configured_token_budgets(
                2400,
                4000,
                retry_env="RAG_EVAL_EMPTY_RESPONSE_RETRIES",
            ),
            evaluation=True,
        )
        try:
            judged = json.loads(judge_text)
        except json.JSONDecodeError as exc:
            raise LLMError(
                "OpenAI comparison judge returned invalid JSON"
            ) from exc
        if not _has_korean_rationale(judged.get("rationale")):
            translated_text, translated_responses = create_text_response(
                client=self._client,
                label="OpenAI comparison rationale translator",
                request={
                    "model": self.judge_model,
                    "input": [
                        {
                            "role": "system",
                            "content": KOREAN_RATIONALE_PROMPT,
                        },
                        {
                            "role": "user",
                            "content": json.dumps(
                                judged,
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                        },
                    ],
                    "text": {
                        "format": {
                            "type": "json_schema",
                            "name": "korean_comparison_rationale",
                            "schema": KOREAN_RATIONALE_SCHEMA,
                            "strict": True,
                        }
                    },
                },
                token_budgets=configured_token_budgets(
                    1400,
                    2400,
                    retry_env="RAG_EVAL_EMPTY_RESPONSE_RETRIES",
                ),
                evaluation=True,
            )
            judge_responses.extend(translated_responses)
            try:
                translated = json.loads(translated_text)
            except json.JSONDecodeError as exc:
                raise LLMError(
                    "OpenAI rationale translator returned invalid JSON"
                ) from exc
            if not _has_korean_rationale(translated.get("rationale")):
                raise LLMError(
                    "OpenAI comparison rationale was not returned in Korean"
                )
            judged["rationale"] = translated["rationale"]

        raw_baseline_scores = {
            name: int(judged["answer_a"][name])
            for name in COMPARISON_CRITERIA
        }
        raw_rag_scores = {
            name: int(judged["answer_b"][name])
            for name in COMPARISON_CRITERIA
        }
        baseline_scores, baseline_notes = _apply_score_guardrails(
            raw_baseline_scores,
            facts=baseline_facts,
            request_facts=request_facts,
            answer_label="답변 A",
        )
        rag_scores, rag_notes = _apply_score_guardrails(
            raw_rag_scores,
            facts=rag_facts,
            request_facts=request_facts,
            answer_label="답변 B",
        )
        baseline_overall = _weighted_score(baseline_scores)
        rag_overall = _weighted_score(rag_scores)
        difference = round(rag_overall - baseline_overall, 2)
        winner = (
            "tie"
            if abs(difference) < 3
            else ("rag" if difference > 0 else "baseline")
        )
        return AnswerComparison(
            question=prompt,
            baseline=ComparedAnswer(
                label="LLM only",
                answer=baseline_answer,
                scores=baseline_scores,
                overall_score=baseline_overall,
            ),
            rag=ComparedAnswer(
                label="RAG + LLM",
                answer=rag_answer,
                scores=rag_scores,
                overall_score=rag_overall,
            ),
            winner=winner,
            score_difference=abs(difference),
            rationale=tuple(
                [
                    *(str(item) for item in judged["rationale"]),
                    *baseline_notes,
                    *rag_notes,
                ]
            ),
            baseline_model=self.baseline_model,
            judge_model=self.judge_model,
            usage={
                "baseline": summed_usage(baseline_responses),
                "judge": summed_usage(judge_responses),
            },
        )
