from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from src.rag.evaluation import (
    EvalCase,
    OpenAIItineraryJudge,
    build_report,
    evaluate_case,
    load_eval_cases,
    report_as_markdown,
)


FIXTURE = Path(__file__).parents[2] / "evals" / "rag" / "golden_cases.jsonl"


def _case() -> EvalCase:
    return EvalCase.from_mapping(
        {
            "id": "perfect",
            "stage": "end_to_end",
            "expected": {
                "status": "completed",
                "conditions": {
                    "duration_days": 1,
                    "preferred_visit_types": ["nature", "culture"],
                },
                "duration_days": 1,
                "tourism_places_per_day": 3,
                "relevant_content_ids": [1, 2],
                "required_content_ids": [1],
                "retrieval_k": 2,
                "context_precision_threshold": 1.0,
                "context_recall_threshold": 1.0,
                "require_valid_schedule": True,
                "forbidden_keywords": ["리조트"],
                "max_validation_warnings": 0,
            },
        }
    )


def _result() -> dict:
    candidates = [
        {
            "content_id": content_id,
            "title": title,
        }
        for content_id, title in (
            (1, "한라수목원"),
            (2, "제주민속촌"),
            (3, "섭지코지"),
        )
    ]
    itinerary = [
        {
            "day": 1,
            "sequence": sequence,
            "content_id": candidate["content_id"],
            "title": candidate["title"],
            "slot_kind": "tourism",
            "description": f"{candidate['title']}에 대한 간략한 설명입니다.",
            "selection_reason": "사용자의 자연·문화 선호와 동선에 맞습니다.",
            "route_verified": sequence > 1,
        }
        for sequence, candidate in enumerate(candidates, start=1)
    ]
    return {
        "status": "completed",
        "conditions": {
            "duration_days": 1,
            "preferred_visit_types": ["culture", "nature"],
            "excluded_places": ["리조트"],
        },
        "slot_candidates": [
            {"slot": {"day": 1, "sequence": index}, "candidates": [candidate]}
            for index, candidate in enumerate(candidates, start=1)
        ],
        "itinerary": itinerary,
        "validation": {"valid": True, "issues": [], "warnings": []},
    }


def test_load_golden_set() -> None:
    cases = load_eval_cases(FIXTURE)
    assert len(cases) >= 8
    assert {case.stage for case in cases} == {"conditions", "end_to_end"}


def test_perfect_result_passes_deterministic_metrics() -> None:
    evaluation = evaluate_case(_case(), _result())
    assert evaluation.passed
    assert evaluation.score == 1.0
    assert not evaluation.failure_tags


def test_hallucinated_id_and_excluded_place_fail_gates() -> None:
    result = _result()
    result["itinerary"][2]["content_id"] = 999
    result["itinerary"][2]["title"] = "가상 리조트"
    evaluation = evaluate_case(_case(), result)
    assert not evaluation.passed
    assert "tourapi_whitelist_grounding" in evaluation.failure_tags
    assert "exclusion_compliance" in evaluation.failure_tags


def test_report_aggregates_failure_tags_and_markdown() -> None:
    passed = evaluate_case(_case(), _result())
    failed_result = _result()
    failed_result["validation"]["valid"] = False
    failed = evaluate_case(
        EvalCase(
            **{**_case().__dict__, "case_id": "failed"}
        ),
        failed_result,
    )
    report = build_report([passed, failed], pass_threshold=0.5)
    payload = report.to_dict()
    assert payload["case_count"] == 2
    assert payload["pass_rate"] == 0.5
    assert "valid_schedule" in payload["failure_counts"]
    assert "| `perfect` | PASS |" in report_as_markdown(report)


class _FakeResponses:
    def create(self, **kwargs):
        assert kwargs["text"]["format"]["strict"] is True
        return SimpleNamespace(
            output_text=json.dumps(
                {
                    "instruction_following": True,
                    "condition_fit": True,
                    "route_coherence": True,
                    "explanation_quality": True,
                    "overall_pass": True,
                    "reasons": ["모든 기준을 충족했습니다."],
                    "failure_tags": [],
                }
            ),
            usage=SimpleNamespace(
                input_tokens=100,
                output_tokens=40,
                total_tokens=140,
            ),
        )


def test_optional_llm_judge_uses_strict_pass_fail_schema() -> None:
    client = SimpleNamespace(responses=_FakeResponses())
    judge = OpenAIItineraryJudge(model="judge-test", client=client)
    evaluation = evaluate_case(_case(), _result(), judge=judge)
    assert evaluation.passed
    assert evaluation.judge is not None
    assert evaluation.judge.model == "judge-test"
    assert evaluation.judge.usage["total_tokens"] == 140
