"""Task-specific, repeatable evaluation utilities for the itinerary RAG.

The evaluators intentionally run locally and do not depend on the OpenAI Evals
API.  Objective checks are deterministic; subjective grading is an optional
second layer that can be calibrated against human labels.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import math
import os
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Mapping, Protocol, Sequence


DEFAULT_PASS_THRESHOLD = 0.80
DEFAULT_CONTEXT_PRECISION_THRESHOLD = 0.70
DEFAULT_CONTEXT_RECALL_THRESHOLD = 0.85


def _normalized(value: Any) -> str:
    return "".join(
        character.lower()
        for character in str(value or "")
        if character.isalnum()
    )


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return value
    return ()


def _int_set(values: Any) -> set[int]:
    result: set[int] = set()
    for value in _as_sequence(values):
        try:
            result.add(int(value))
        except (TypeError, ValueError):
            continue
    return result


def _string_set(values: Any) -> set[str]:
    if isinstance(values, str):
        values = (values,)
    return {
        normalized
        for value in _as_sequence(values)
        if (normalized := _normalized(value))
    }


def _f1(expected: set[Any], actual: set[Any]) -> float:
    if not expected and not actual:
        return 1.0
    if not expected or not actual:
        return 0.0
    overlap = len(expected & actual)
    precision = overlap / len(actual)
    recall = overlap / len(expected)
    return (
        0.0
        if precision + recall == 0
        else 2 * precision * recall / (precision + recall)
    )


@dataclass(frozen=True)
class EvalCase:
    """One human-curated golden-set example."""

    case_id: str
    stage: str
    message: str = ""
    history: tuple[Mapping[str, str], ...] = ()
    current_conditions: Mapping[str, Any] = field(default_factory=dict)
    selected_options: Mapping[str, Any] = field(default_factory=dict)
    expected: Mapping[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "EvalCase":
        case_id = str(value.get("id") or value.get("case_id") or "").strip()
        if not case_id:
            raise ValueError("eval case needs a non-empty id")
        stage = str(value.get("stage") or "end_to_end").strip()
        if stage not in {"conditions", "end_to_end"}:
            raise ValueError(f"unsupported eval stage: {stage}")
        history = tuple(
            dict(item)
            for item in _as_sequence(value.get("history"))
            if isinstance(item, Mapping)
        )
        return cls(
            case_id=case_id,
            stage=stage,
            message=str(value.get("message") or ""),
            history=history,
            current_conditions=dict(
                _as_mapping(value.get("current_conditions"))
            ),
            selected_options=dict(
                _as_mapping(value.get("selected_options"))
            ),
            expected=dict(_as_mapping(value.get("expected"))),
            tags=tuple(str(item) for item in _as_sequence(value.get("tags"))),
        )


@dataclass(frozen=True)
class MetricResult:
    name: str
    value: float
    passed: bool
    threshold: float
    gate: bool = False
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class JudgeResult:
    passed: bool
    criteria: Mapping[str, bool]
    reasons: tuple[str, ...] = ()
    failure_tags: tuple[str, ...] = ()
    model: str = ""
    usage: Mapping[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["criteria"] = dict(self.criteria)
        payload["reasons"] = list(self.reasons)
        payload["failure_tags"] = list(self.failure_tags)
        payload["usage"] = dict(self.usage)
        return payload


@dataclass(frozen=True)
class CaseEvaluation:
    case_id: str
    passed: bool
    score: float
    metrics: tuple[MetricResult, ...]
    failure_tags: tuple[str, ...]
    result_status: str
    latency_ms: float | None = None
    judge: JudgeResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "score": self.score,
            "metrics": [metric.to_dict() for metric in self.metrics],
            "failure_tags": list(self.failure_tags),
            "result_status": self.result_status,
            "latency_ms": self.latency_ms,
            "judge": self.judge.to_dict() if self.judge else None,
        }


@dataclass(frozen=True)
class EvaluationReport:
    cases: tuple[CaseEvaluation, ...]
    pass_threshold: float = DEFAULT_PASS_THRESHOLD

    @property
    def pass_rate(self) -> float:
        return (
            mean(1.0 if case.passed else 0.0 for case in self.cases)
            if self.cases
            else 0.0
        )

    @property
    def average_score(self) -> float:
        return mean(case.score for case in self.cases) if self.cases else 0.0

    @property
    def passed(self) -> bool:
        return bool(self.cases) and self.pass_rate >= self.pass_threshold

    def metric_averages(self) -> dict[str, float]:
        grouped: dict[str, list[float]] = {}
        for case in self.cases:
            for metric in case.metrics:
                grouped.setdefault(metric.name, []).append(metric.value)
        return {
            name: round(mean(values), 6)
            for name, values in sorted(grouped.items())
        }

    def failure_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for case in self.cases:
            for tag in case.failure_tags:
                counts[tag] = counts.get(tag, 0) + 1
        return dict(sorted(counts.items()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "case_count": len(self.cases),
            "pass_threshold": self.pass_threshold,
            "pass_rate": round(self.pass_rate, 6),
            "average_score": round(self.average_score, 6),
            "metric_averages": self.metric_averages(),
            "failure_counts": self.failure_counts(),
            "cases": [case.to_dict() for case in self.cases],
        }


class ItineraryJudge(Protocol):
    def grade(
        self,
        *,
        case: EvalCase,
        result: Mapping[str, Any],
    ) -> JudgeResult: ...


def load_eval_cases(path: str | Path) -> list[EvalCase]:
    """Load a JSONL golden set."""

    source = Path(path)
    cases: list[EvalCase] = []
    for line_number, raw_line in enumerate(
        source.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{source}:{line_number}: invalid JSON: {exc}"
            ) from exc
        if not isinstance(payload, Mapping):
            raise ValueError(
                f"{source}:{line_number}: eval case must be an object"
            )
        cases.append(EvalCase.from_mapping(payload))
    if not cases:
        raise ValueError(f"eval dataset is empty: {source}")
    duplicate_ids = {
        case.case_id
        for case in cases
        if sum(item.case_id == case.case_id for item in cases) > 1
    }
    if duplicate_ids:
        raise ValueError(
            "duplicate eval case ids: " + ", ".join(sorted(duplicate_ids))
        )
    return cases


def evaluate_case(
    case: EvalCase,
    result: Mapping[str, Any],
    *,
    latency_ms: float | None = None,
    judge: ItineraryJudge | None = None,
    pass_threshold: float = DEFAULT_PASS_THRESHOLD,
) -> CaseEvaluation:
    """Score one result with deterministic checks and an optional LLM judge."""

    metrics = (
        _condition_metrics(case, result)
        if case.stage == "conditions"
        else [
            *_condition_metrics(case, result),
            *_retrieval_metrics(case, result),
            *_itinerary_metrics(case, result),
        ]
    )
    score = mean(metric.value for metric in metrics) if metrics else 0.0
    gate_failed = any(metric.gate and not metric.passed for metric in metrics)
    judge_result = judge.grade(case=case, result=result) if judge else None
    passed = (
        bool(metrics)
        and score >= pass_threshold
        and not gate_failed
        and (judge_result is None or judge_result.passed)
    )
    failure_tags = [
        metric.name
        for metric in metrics
        if not metric.passed
    ]
    if judge_result:
        failure_tags.extend(judge_result.failure_tags)
    return CaseEvaluation(
        case_id=case.case_id,
        passed=passed,
        score=round(score, 6),
        metrics=tuple(metrics),
        failure_tags=tuple(dict.fromkeys(failure_tags)),
        result_status=str(result.get("status") or ""),
        latency_ms=round(latency_ms, 3) if latency_ms is not None else None,
        judge=judge_result,
    )


def build_report(
    evaluations: Iterable[CaseEvaluation],
    *,
    pass_threshold: float = DEFAULT_PASS_THRESHOLD,
) -> EvaluationReport:
    return EvaluationReport(tuple(evaluations), pass_threshold)


def _metric(
    name: str,
    value: float,
    threshold: float,
    *,
    gate: bool = False,
    details: Mapping[str, Any] | None = None,
) -> MetricResult:
    finite_value = value if math.isfinite(value) else 0.0
    return MetricResult(
        name=name,
        value=round(max(0.0, min(1.0, finite_value)), 6),
        passed=finite_value >= threshold,
        threshold=threshold,
        gate=gate,
        details=dict(details or {}),
    )


def _condition_metrics(
    case: EvalCase,
    result: Mapping[str, Any],
) -> list[MetricResult]:
    expected = _as_mapping(case.expected)
    expected_conditions = _as_mapping(expected.get("conditions"))
    actual_conditions = _as_mapping(result.get("conditions"))
    metrics: list[MetricResult] = []

    expected_statuses = expected.get("statuses")
    if expected_statuses is None and expected.get("status") is not None:
        expected_statuses = [expected.get("status")]
    if expected_statuses:
        allowed = {str(item) for item in _as_sequence(expected_statuses)}
        actual_status = str(result.get("status") or "")
        metrics.append(
            _metric(
                "expected_status",
                1.0 if actual_status in allowed else 0.0,
                1.0,
                gate=True,
                details={"expected": sorted(allowed), "actual": actual_status},
            )
        )

    scalar_scores: list[float] = []
    list_scores: list[float] = []
    scalar_details: dict[str, Any] = {}
    list_details: dict[str, Any] = {}
    for field_name, expected_value in expected_conditions.items():
        actual_value = actual_conditions.get(field_name)
        if isinstance(expected_value, list):
            expected_set = _string_set(expected_value)
            actual_set = _string_set(actual_value)
            score = _f1(expected_set, actual_set)
            list_scores.append(score)
            list_details[field_name] = {
                "expected": sorted(expected_set),
                "actual": sorted(actual_set),
                "f1": round(score, 6),
            }
        else:
            score = 1.0 if actual_value == expected_value else 0.0
            scalar_scores.append(score)
            scalar_details[field_name] = {
                "expected": expected_value,
                "actual": actual_value,
            }
    if scalar_scores:
        metrics.append(
            _metric(
                "condition_scalar_accuracy",
                mean(scalar_scores),
                float(expected.get("condition_scalar_threshold", 1.0)),
                gate=True,
                details=scalar_details,
            )
        )
    if list_scores:
        metrics.append(
            _metric(
                "condition_list_f1",
                mean(list_scores),
                float(expected.get("condition_list_threshold", 0.8)),
                gate=True,
                details=list_details,
            )
        )
    return metrics


def _flatten_candidates(
    result: Mapping[str, Any],
) -> tuple[list[int], dict[int, Mapping[str, Any]]]:
    ordered: list[int] = []
    places: dict[int, Mapping[str, Any]] = {}
    for slot in _as_sequence(result.get("slot_candidates")):
        if not isinstance(slot, Mapping):
            continue
        for candidate in _as_sequence(slot.get("candidates")):
            if not isinstance(candidate, Mapping):
                continue
            try:
                content_id = int(candidate.get("content_id"))
            except (TypeError, ValueError):
                continue
            if content_id not in places:
                ordered.append(content_id)
                places[content_id] = candidate
    return ordered, places


def _retrieval_metrics(
    case: EvalCase,
    result: Mapping[str, Any],
) -> list[MetricResult]:
    expected = _as_mapping(case.expected)
    relevant = _int_set(expected.get("relevant_content_ids"))
    if not relevant:
        return []
    ordered, _ = _flatten_candidates(result)
    top_k = int(expected.get("retrieval_k") or len(ordered) or 1)
    retrieved = ordered[:top_k]
    retrieved_set = set(retrieved)
    matches = retrieved_set & relevant
    precision = len(matches) / len(retrieved_set) if retrieved_set else 0.0
    recall = len(matches) / len(relevant)
    reciprocal_rank = 0.0
    for rank, content_id in enumerate(retrieved, start=1):
        if content_id in relevant:
            reciprocal_rank = 1.0 / rank
            break
    return [
        _metric(
            "context_precision",
            precision,
            float(
                expected.get(
                    "context_precision_threshold",
                    DEFAULT_CONTEXT_PRECISION_THRESHOLD,
                )
            ),
            details={
                "relevant": sorted(relevant),
                "retrieved": retrieved,
                "matched": sorted(matches),
            },
        ),
        _metric(
            "context_recall",
            recall,
            float(
                expected.get(
                    "context_recall_threshold",
                    DEFAULT_CONTEXT_RECALL_THRESHOLD,
                )
            ),
            gate=True,
            details={
                "relevant": sorted(relevant),
                "matched": sorted(matches),
            },
        ),
        _metric(
            "retrieval_mrr",
            reciprocal_rank,
            float(expected.get("mrr_threshold", 0.5)),
        ),
    ]


def _itinerary_metrics(
    case: EvalCase,
    result: Mapping[str, Any],
) -> list[MetricResult]:
    expected = _as_mapping(case.expected)
    itinerary = [
        item
        for item in _as_sequence(result.get("itinerary"))
        if isinstance(item, Mapping)
    ]
    conditions = _as_mapping(result.get("conditions"))
    validation = _as_mapping(result.get("validation"))
    metrics: list[MetricResult] = []

    if "require_valid_schedule" in expected:
        actual_valid = bool(validation.get("valid"))
        expected_valid = bool(expected.get("require_valid_schedule"))
        metrics.append(
            _metric(
                "valid_schedule",
                1.0 if actual_valid == expected_valid else 0.0,
                1.0,
                gate=True,
                details={"expected": expected_valid, "actual": actual_valid},
            )
        )

    requested_days = int(
        expected.get("duration_days")
        or conditions.get("duration_days")
        or 0
    )
    if requested_days:
        actual_days = {
            int(item.get("day") or 0)
            for item in itinerary
            if int(item.get("day") or 0) > 0
        }
        expected_days = set(range(1, requested_days + 1))
        metrics.append(
            _metric(
                "day_coverage",
                len(actual_days & expected_days) / len(expected_days),
                1.0,
                gate=True,
                details={
                    "expected_days": sorted(expected_days),
                    "actual_days": sorted(actual_days),
                },
            )
        )

    places_per_day = expected.get("tourism_places_per_day")
    if places_per_day is not None and requested_days:
        expected_count = int(places_per_day)
        counts = {
            day: sum(
                1
                for item in itinerary
                if int(item.get("day") or 0) == day
                and str(item.get("slot_kind") or "tourism") != "meal"
            )
            for day in range(1, requested_days + 1)
        }
        correct = sum(
            1 for count in counts.values() if count == expected_count
        )
        metrics.append(
            _metric(
                "places_per_day_accuracy",
                correct / requested_days,
                1.0,
                gate=True,
                details={
                    "expected_per_day": expected_count,
                    "actual_counts": counts,
                },
            )
        )

    candidate_ids, _ = _flatten_candidates(result)
    candidate_set = set(candidate_ids)
    itinerary_ids = _int_set(
        [
            item.get("content_id")
            for item in itinerary
            if item.get("content_id") is not None
        ]
    )
    grounded = itinerary_ids & candidate_set
    grounding = (
        len(grounded) / len(itinerary_ids)
        if itinerary_ids
        else 0.0
    )
    metrics.append(
        _metric(
            "tourapi_whitelist_grounding",
            grounding,
            1.0,
            gate=True,
            details={
                "itinerary_ids": sorted(itinerary_ids),
                "outside_whitelist": sorted(itinerary_ids - candidate_set),
            },
        )
    )

    if itinerary:
        unique_ratio = len(itinerary_ids) / len(itinerary)
        metrics.append(
            _metric(
                "unique_place_ratio",
                unique_ratio,
                float(expected.get("unique_place_threshold", 1.0)),
                gate=True,
            )
        )
        description_ratio = sum(
            1
            for item in itinerary
            if str(item.get("description") or "").strip()
        ) / len(itinerary)
        reason_ratio = sum(
            1
            for item in itinerary
            if str(
                item.get("selection_reason")
                or item.get("reason")
                or ""
            ).strip()
        ) / len(itinerary)
        metrics.extend(
            [
                _metric(
                    "description_coverage",
                    description_ratio,
                    float(expected.get("description_threshold", 1.0)),
                ),
                _metric(
                    "selection_reason_coverage",
                    reason_ratio,
                    float(expected.get("reason_threshold", 1.0)),
                ),
            ]
        )

    required_ids = (
        _int_set(expected.get("required_content_ids"))
        or _int_set(conditions.get("must_visit_content_ids"))
    )
    required_titles = (
        _string_set(expected.get("required_titles"))
        or _string_set(conditions.get("must_visit_places"))
    )
    actual_titles = {
        _normalized(item.get("title"))
        for item in itinerary
        if _normalized(item.get("title"))
    }
    id_recall = (
        len(required_ids & itinerary_ids) / len(required_ids)
        if required_ids
        else 1.0
    )
    title_matches = {
        required
        for required in required_titles
        if any(
            required in actual or actual in required
            for actual in actual_titles
        )
    }
    title_recall = (
        len(title_matches) / len(required_titles)
        if required_titles
        else 1.0
    )
    if required_ids or required_titles:
        metrics.append(
            _metric(
                "required_place_recall",
                mean([id_recall, title_recall]),
                1.0,
                gate=True,
                details={
                    "missing_content_ids": sorted(
                        required_ids - itinerary_ids
                    ),
                    "missing_titles": sorted(
                        required_titles - title_matches
                    ),
                },
            )
        )

    forbidden = (
        _string_set(expected.get("forbidden_keywords"))
        | _string_set(conditions.get("excluded_places"))
        | _string_set(conditions.get("excluded_foods"))
    )
    violations = sorted(
        {
            keyword
            for keyword in forbidden
            if any(
                keyword
                in _normalized(
                    " ".join(
                        str(item.get(field) or "")
                        for field in (
                            "title",
                            "description",
                            "selection_reason",
                            "reason",
                        )
                    )
                )
                for item in itinerary
            )
        }
    )
    if forbidden:
        metrics.append(
            _metric(
                "exclusion_compliance",
                1.0 if not violations else 0.0,
                1.0,
                gate=True,
                details={"violations": violations},
            )
        )

    max_warnings = expected.get("max_validation_warnings")
    if max_warnings is not None:
        warnings = len(_as_sequence(validation.get("warnings")))
        limit = int(max_warnings)
        metrics.append(
            _metric(
                "validation_warning_limit",
                1.0 if warnings <= limit else 0.0,
                1.0,
                gate=True,
                details={"limit": limit, "actual": warnings},
            )
        )

    if expected.get("require_verified_routes") and itinerary:
        route_legs = itinerary[1:]
        verified = sum(
            1 for item in route_legs if bool(item.get("route_verified"))
        )
        ratio = verified / len(route_legs) if route_legs else 1.0
        metrics.append(
            _metric(
                "verified_route_coverage",
                ratio,
                1.0,
                gate=True,
            )
        )
    return metrics


JUDGE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "instruction_following": {"type": "boolean"},
        "condition_fit": {"type": "boolean"},
        "route_coherence": {"type": "boolean"},
        "explanation_quality": {"type": "boolean"},
        "overall_pass": {"type": "boolean"},
        "reasons": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 5,
        },
        "failure_tags": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 5,
        },
    },
    "required": [
        "instruction_following",
        "condition_fit",
        "route_coherence",
        "explanation_quality",
        "overall_pass",
        "reasons",
        "failure_tags",
    ],
}


JUDGE_SYSTEM_PROMPT = """\
당신은 제주 여행 일정 평가자다. 결과를 새로 생성하지 말고 주어진 일정만 평가한다.
각 기준은 모호한 1~5점 대신 엄격한 통과/실패로 판정한다.

판정 기준:
1. instruction_following: 사용자의 명시적 일정·장소 수·제외 요청을 지켰다.
2. condition_fit: 동행자, 교통, 선호, 필수 장소 조건과 일정이 부합한다.
3. route_coherence: 시간 순서가 유효하고 같은 날의 이동 흐름이 명백히 부자연스럽지 않다.
4. explanation_quality: 각 장소 설명과 선택 이유가 구체적이며 서로 구분된다.
5. overall_pass: 위 네 기준이 모두 통과한 경우에만 true다.

제공되지 않은 사실을 추정하지 않는다. 좌표·운영시간·화이트리스트·필수 장소
준수는 결정론적 채점기가 담당하므로, 입력에 없는 근거로 판단하지 않는다.
"""


class OpenAIItineraryJudge:
    """Optional pass/fail judge; calibrate it against human labels before CI use."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.model = (
            model
            or os.getenv("OPENAI_EVAL_JUDGE_MODEL")
            or os.getenv("OPENAI_CHAT_MODEL")
            or "gpt-5-mini"
        )
        if client is None:
            key = api_key or os.getenv("OPENAI_API_KEY", "")
            if not key:
                raise RuntimeError(
                    "OPENAI_API_KEY is required for --llm-judge"
                )
            from openai import OpenAI

            client = OpenAI(api_key=key, timeout=60.0)
        self._client = client

    def grade(
        self,
        *,
        case: EvalCase,
        result: Mapping[str, Any],
    ) -> JudgeResult:
        payload = {
            "user_message": case.message,
            "selected_options": dict(case.selected_options),
            "expected_rubric": dict(case.expected),
            "actual_conditions": dict(
                _as_mapping(result.get("conditions"))
            ),
            "itinerary": list(_as_sequence(result.get("itinerary"))),
            "validation": dict(_as_mapping(result.get("validation"))),
        }
        from .openai_responses import create_text_response, summed_usage

        output_text, responses = create_text_response(
            client=self._client,
            label="OpenAI itinerary judge",
            request={
                "model": self.model,
                "input": [
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False),
                    },
                ],
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "rag_itinerary_eval",
                        "schema": JUDGE_OUTPUT_SCHEMA,
                        "strict": True,
                    }
                },
            },
            token_budgets=(4000, 8000),
            evaluation=True,
        )
        parsed = json.loads(output_text)
        criteria = {
            name: bool(parsed[name])
            for name in (
                "instruction_following",
                "condition_fit",
                "route_coherence",
                "explanation_quality",
            )
        }
        usage_payload = summed_usage(responses)
        return JudgeResult(
            passed=bool(parsed["overall_pass"]) and all(criteria.values()),
            criteria=criteria,
            reasons=tuple(str(item) for item in parsed["reasons"]),
            failure_tags=tuple(
                str(item) for item in parsed["failure_tags"]
            ),
            model=self.model,
            usage=usage_payload,
        )


def report_as_markdown(report: EvaluationReport) -> str:
    lines = [
        "# RAG 평가 결과",
        "",
        f"- 전체 통과: {'예' if report.passed else '아니오'}",
        f"- 케이스 수: {len(report.cases)}",
        f"- 통과율: {report.pass_rate:.1%}",
        f"- 평균 점수: {report.average_score:.3f}",
        "",
        "## 지표 평균",
        "",
        "| 지표 | 평균 |",
        "|---|---:|",
    ]
    for name, value in report.metric_averages().items():
        lines.append(f"| `{name}` | {value:.3f} |")
    lines.extend(
        [
            "",
            "## 케이스",
            "",
            "| ID | 통과 | 점수 | 상태 | 실패 태그 |",
            "|---|---:|---:|---|---|",
        ]
    )
    for case in report.cases:
        failure_tags = ", ".join(case.failure_tags) or "-"
        lines.append(
            f"| `{case.case_id}` | "
            f"{'PASS' if case.passed else 'FAIL'} | "
            f"{case.score:.3f} | `{case.result_status}` | {failure_tags} |"
        )
    return "\n".join(lines) + "\n"
