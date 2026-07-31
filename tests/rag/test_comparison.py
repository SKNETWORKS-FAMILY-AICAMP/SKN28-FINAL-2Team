from __future__ import annotations

import json
from types import SimpleNamespace

from src.rag.comparison import (
    AnswerComparison,
    COMPARISON_CRITERIA,
    ComparedAnswer,
    OpenAIResponseComparator,
    format_rag_answer,
    summarize_answer_comparisons,
)


class _FakeResponses:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        value = self.outputs.pop(0)
        if isinstance(value, dict):
            output_text = value.get("output_text")
            status = value.get("status", "completed")
            reason = value.get("reason")
        else:
            output_text = value
            status = "completed"
            reason = None
        return SimpleNamespace(
            output_text=output_text,
            status=status,
            incomplete_details=SimpleNamespace(reason=reason),
            usage=SimpleNamespace(
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
            ),
        )


class _FakeClient:
    def __init__(self, outputs):
        self.responses = _FakeResponses(outputs)


def test_format_rag_answer_includes_schedule_grounding_and_validation():
    answer = format_rag_answer(
        {
            "status": "completed",
            "message": "검증된 일정입니다.",
            "itinerary": [
                {
                    "day": 1,
                    "start_time": "09:00",
                    "end_time": "10:30",
                    "title": "한라수목원",
                    "content_id": 127514,
                    "source": "TourAPI",
                    "description": "제주 자생식물을 볼 수 있는 수목원입니다.",
                    "selection_reason": "부모님과 걷기 좋은 자연 명소입니다.",
                }
            ],
            "validation": {"valid": True, "issues": []},
        }
    )

    assert "한라수목원" in answer
    assert "TourAPI ID 127514" in answer
    assert "설명:" in answer
    assert "선택 이유:" in answer
    assert "valid=True" in answer


def test_comparator_scores_no_rag_and_rag_answers_anonymously():
    judged = {
        "answer_a": {
            "instruction_following": 60,
            "answer_completeness": 40,
            "relevance": 80,
            "grounding": 30,
            "itinerary_feasibility": 50,
            "explanation_quality": 70,
        },
        "answer_b": {
            "instruction_following": 90,
            "answer_completeness": 90,
            "relevance": 90,
            "grounding": 95,
            "itinerary_feasibility": 90,
            "explanation_quality": 85,
        },
        "rationale": ["RAG 답변에 장소 ID와 검증 결과가 포함되어 있습니다."],
    }
    client = _FakeClient(
        [
            "검색 없이 작성한 기본 LLM 답변",
            json.dumps(judged, ensure_ascii=False),
        ]
    )
    comparator = OpenAIResponseComparator(
        baseline_model="gpt-5-mini",
        judge_model="gpt-5-mini",
        client=client,
    )

    result = comparator.compare(
        question="부모님과 제주 1일 자연 여행을 추천해 주세요.",
        rag_result={
            "status": "clarification_required",
            "message": "교통수단을 알려주세요.",
            "clarification_questions": ["어떤 교통수단을 이용하시나요?"],
        },
    )

    assert result.winner == "rag"
    assert result.rag.overall_score > result.baseline.overall_score
    assert result.baseline.answer == "검색 없이 작성한 기본 LLM 답변"
    assert result.usage["baseline"]["total_tokens"] == 150
    assert result.usage["judge"]["total_tokens"] == 150
    assert len(client.responses.calls) == 2
    judge_call = client.responses.calls[1]
    assert judge_call["text"]["format"]["type"] == "json_schema"
    assert judge_call["reasoning"] == {"effort": "minimal"}
    judge_payload = json.loads(judge_call["input"][1]["content"])
    assert judge_payload["answer_a"] == result.baseline.answer
    assert "상태: clarification_required" in judge_payload["answer_b"]


def test_comparator_retries_empty_judge_output_and_counts_usage(monkeypatch):
    monkeypatch.setenv("RAG_EVAL_EMPTY_RESPONSE_RETRIES", "1")
    criteria = COMPARISON_CRITERIA
    judged = {
        "answer_a": {name: 50 for name in criteria},
        "answer_b": {name: 80 for name in criteria},
        "rationale": ["RAG 답변은 검색 근거가 더 명확합니다."],
    }
    client = _FakeClient(
        [
            "baseline",
            {
                "output_text": None,
                "status": "incomplete",
                "reason": "max_output_tokens",
            },
            json.dumps(judged),
        ]
    )
    comparator = OpenAIResponseComparator(client=client)

    result = comparator.compare(
        question="Jeju itinerary",
        rag_result={"status": "completed", "itinerary": []},
    )

    assert result.winner == "rag"
    assert len(client.responses.calls) == 3
    assert client.responses.calls[1]["max_output_tokens"] == 2400
    assert client.responses.calls[2]["max_output_tokens"] == 4000
    assert result.usage["judge"]["total_tokens"] == 300


def test_comparator_rewrites_english_rationale_in_korean():
    criteria = COMPARISON_CRITERIA
    judged = {
        "answer_a": {name: 50 for name in criteria},
        "answer_b": {name: 80 for name in criteria},
        "rationale": ["Answer B is better grounded."],
    }
    translated = {
        "rationale": ["답변 B는 장소 식별자와 출처가 있어 근거가 더 명확합니다."]
    }
    client = _FakeClient(
        [
            "baseline",
            json.dumps(judged),
            json.dumps(translated, ensure_ascii=False),
        ]
    )

    result = OpenAIResponseComparator(client=client).compare(
        question="Jeju itinerary",
        rag_result={"status": "completed", "itinerary": []},
    )

    assert result.rationale == tuple(translated["rationale"])
    assert len(client.responses.calls) == 3
    translation_call = client.responses.calls[2]
    assert (
        translation_call["text"]["format"]["name"]
        == "korean_comparison_rationale"
    )
    assert result.usage["judge"]["total_tokens"] == 300


def test_summarize_answer_comparisons_reports_stability_and_win_counts():
    def comparison(
        baseline_score: float,
        rag_score: float,
        winner: str,
    ) -> AnswerComparison:
        baseline_criteria = {
            name: int(baseline_score)
            for name in COMPARISON_CRITERIA
        }
        rag_criteria = {
            name: int(rag_score)
            for name in baseline_criteria
        }
        return AnswerComparison(
            question="질문",
            baseline=ComparedAnswer(
                label="LLM only",
                answer="baseline",
                scores=baseline_criteria,
                overall_score=baseline_score,
            ),
            rag=ComparedAnswer(
                label="RAG + LLM",
                answer="rag",
                scores=rag_criteria,
                overall_score=rag_score,
            ),
            winner=winner,
            score_difference=abs(rag_score - baseline_score),
            rationale=("근거",),
            baseline_model="gpt-5-mini",
            judge_model="gpt-5-mini",
            usage={},
        )

    summary = summarize_answer_comparisons(
        [
            comparison(60, 80, "rag"),
            comparison(70, 80, "rag"),
            comparison(80, 80, "tie"),
        ]
    )

    assert summary["run_count"] == 3
    assert summary["baseline"]["mean"] == 70
    assert summary["baseline"]["stddev"] > 0
    assert summary["rag"]["stddev"] == 0
    assert summary["average_improvement"] == 10
    assert summary["win_counts"] == {"baseline": 0, "rag": 2, "tie": 1}


def test_itinerary_guardrails_penalize_clarification_only_and_ignore_meals():
    judged = {
        "answer_a": {name: 95 for name in COMPARISON_CRITERIA},
        "answer_b": {name: 70 for name in COMPARISON_CRITERIA},
        "rationale": ["답변 A와 답변 B를 제공된 기준으로 비교했습니다."],
    }
    itinerary = []
    content_id = 1000
    for day in range(1, 4):
        for sequence in range(1, 4):
            content_id += 1
            itinerary.append(
                {
                    "day": day,
                    "sequence": sequence,
                    "content_id": content_id,
                    "title": f"관광지 {day}-{sequence}",
                    "start_time": "09:00",
                    "end_time": "10:00",
                    "slot_kind": "tourism",
                    "description": "관광지 설명",
                    "selection_reason": "선택 이유",
                }
            )
        for meal_type in ("lunch", "dinner"):
            content_id += 1
            itinerary.append(
                {
                    "day": day,
                    "sequence": 10,
                    "content_id": content_id,
                    "title": f"{meal_type} 식당",
                    "start_time": "12:00",
                    "end_time": "13:00",
                    "slot_kind": "meal",
                    "meal_type": meal_type,
                    "description": "식당 설명",
                    "selection_reason": "식사 장소 선택 이유",
                }
            )
    client = _FakeClient(
        [
            "숙소와 도착 시간을 알려주시면 일정을 제안드릴게요.",
            json.dumps(judged, ensure_ascii=False),
        ]
    )

    result = OpenAIResponseComparator(client=client).compare(
        question=(
            "부모님과 렌터카로 제주 2박 3일 여행을 갑니다. "
            "자연과 문화를 좋아합니다. 관광지를 하루 3곳씩 추천해 주세요."
        ),
        rag_result={
            "status": "completed",
            "conditions": {
                "duration_days": 3,
                "party_type": "with_parents",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature", "culture"],
            },
            "itinerary": itinerary,
            "validation": {"valid": True, "issues": []},
        },
    )

    assert result.winner == "rag"
    assert result.baseline.scores["instruction_following"] == 20
    assert result.baseline.scores["answer_completeness"] == 0
    assert result.baseline.scores["itinerary_feasibility"] == 0
    assert result.rag.scores["answer_completeness"] == 100
    judge_payload = json.loads(
        client.responses.calls[1]["input"][1]["content"]
    )
    facts = judge_payload["evaluation_facts"]
    assert facts["request"]["expected_tourism_items"] == 9
    assert facts["request"]["required_conditions_complete"] is True
    assert facts["answer_b"]["tourism_items"] == 9
    assert facts["answer_b"]["meal_items"] == 6
    assert any("식사는 관광지 개수에서 제외" in item for item in result.rationale)
