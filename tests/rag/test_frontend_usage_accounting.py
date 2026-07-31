from __future__ import annotations

from src.rag.comparison import AnswerComparison, ComparedAnswer

import rag_test_frontend.app as frontend


def _usage(stage: str, tokens: int) -> dict:
    return {
        "stage": stage,
        "input_tokens": tokens,
        "output_tokens": 10,
        "total_tokens": tokens + 10,
    }


class _LLM:
    def __init__(self) -> None:
        self.records = [_usage("old_interaction", 100_000)]

    def drain_usage_records(self):
        records = list(self.records)
        self.records.clear()
        return records


class _Rag:
    def __init__(self) -> None:
        self.llm = _LLM()
        self.calls = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("message"):
            self.llm.records.extend(
                [
                    _usage("travel_condition_extraction", 1000),
                    _usage("tourapi_itinerary_draft", 2000),
                ]
            )
        else:
            self.llm.records.append(
                _usage("tourapi_itinerary_draft", 2000)
            )
        return {
            "status": "completed",
            "conditions": {
                "duration_days": 2,
                "party_type": "solo",
                "local_transport": "mixed",
                "preferred_visit_types": ["nature"],
            },
            "itinerary": [{"content_id": 101}],
            "validation": {"valid": True},
        }


class _Comparator:
    def __init__(self, **kwargs) -> None:
        pass

    def compare(self, **kwargs):
        scores = {
            "instruction_following": 80,
            "answer_completeness": 80,
            "relevance": 80,
            "grounding": 80,
            "itinerary_feasibility": 80,
            "explanation_quality": 80,
        }
        return AnswerComparison(
            question=kwargs["question"],
            baseline=ComparedAnswer("LLM only", "baseline", scores, 80),
            rag=ComparedAnswer("RAG + LLM", "rag", scores, 80),
            winner="tie",
            score_difference=0,
            rationale=("동점",),
            baseline_model="test",
            judge_model="test",
            usage={
                "baseline": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "total_tokens": 150,
                },
                "judge": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "total_tokens": 150,
                },
            },
        )


class _Progress:
    def progress(self, *args, **kwargs) -> None:
        pass

    def empty(self) -> None:
        pass


def test_comparison_excludes_stale_usage_and_reuses_conditions(
    monkeypatch,
) -> None:
    rag = _Rag()
    monkeypatch.setattr(frontend, "_rag", lambda: rag)
    monkeypatch.setattr(frontend, "OpenAIResponseComparator", _Comparator)
    monkeypatch.setattr(
        frontend.st,
        "progress",
        lambda *args, **kwargs: _Progress(),
    )

    result = frontend._run_answer_comparison(
        question="제주 2일 여행",
        baseline_model="test",
        judge_model="test",
        repeat_count=3,
    )

    assert result["discarded_preexisting_usage"]["calls"] == 1
    assert result["discarded_preexisting_usage"]["input_tokens"] == 100_000
    assert result["total_usage"]["rag"]["calls"] == 4
    assert result["total_usage"]["rag"]["input_tokens"] == 7000
    assert rag.calls[0]["message"] == "제주 2일 여행"
    assert "selected_options" in rag.calls[1]
    assert "selected_options" in rag.calls[2]
