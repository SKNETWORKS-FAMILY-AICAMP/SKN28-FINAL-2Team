from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.rag.langgraph_workflow import LangGraphRagWorkflow
from src.rag.langsmith_evaluation import (
    deterministic_validation_evaluator,
    itinerary_completion_evaluator,
    required_place_coverage_evaluator,
    run_langsmith_evaluation,
)
from src.rag.langsmith_observability import langsmith_status


class _FakeOrchestrator:
    def __init__(self) -> None:
        self.llm = SimpleNamespace()
        self.condition_service = SimpleNamespace()
        self.calls: list[dict] = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        message = str(kwargs.get("message") or "")
        if "부족" in message:
            return {
                "status": "clarification_required",
                "conditions": {"duration_days": 2},
                "clarification_questions": ["교통수단을 선택해 주세요."],
            }
        return {
            "status": "completed",
            "conditions": {"duration_days": 2, "party_type": "solo"},
            "itinerary": [
                {"day": 1, "content_id": 101, "title": "테스트 장소"}
            ],
            "validation": {"valid": True, "issues": []},
        }

    def revise(self, **kwargs):
        return {
            **dict(kwargs["previous_result"]),
            "status": "completed",
        }


def test_langgraph_routes_completed_and_clarification_paths(monkeypatch) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    workflow = LangGraphRagWorkflow(_FakeOrchestrator())

    completed = workflow.run(message="제주 2일 여행", thread_id="thread-a")
    clarification = workflow.run(message="조건 부족", thread_id="thread-b")

    assert completed["meta"]["langgraph"]["path"] == [
        "prepare_input",
        "execute_rag",
        "finalize_result",
    ]
    assert clarification["meta"]["langgraph"]["path"] == [
        "prepare_input",
        "execute_rag",
        "request_clarification",
    ]
    assert completed["meta"]["langsmith"]["enabled"] is False


def test_langgraph_thread_reuses_prior_conditions() -> None:
    fake = _FakeOrchestrator()
    workflow = LangGraphRagWorkflow(fake)

    workflow.run(message="첫 요청", thread_id="same-thread")
    workflow.run(message="후속 요청", thread_id="same-thread")

    assert fake.calls[1]["current_conditions"] == {
        "duration_days": 2,
        "party_type": "solo",
    }
    snapshot = workflow.get_state("same-thread")
    assert snapshot.values["status"] == "completed"


def test_langsmith_status_never_exposes_key(monkeypatch) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "secret-value")

    payload = langsmith_status().to_dict()

    assert payload["enabled"] is True
    assert payload["api_key_configured"] is True
    assert "secret-value" not in str(payload)


def test_langsmith_contract_evaluators() -> None:
    outputs = {
        "status": "completed",
        "itinerary": [{"content_id": 101}, {"content_id": 102}],
        "validation": {"valid": True},
    }

    assert itinerary_completion_evaluator(outputs=outputs)["score"] == 1.0
    assert deterministic_validation_evaluator(outputs=outputs)["score"] == 1.0
    assert required_place_coverage_evaluator(
        outputs=outputs,
        reference_outputs={"required_content_ids": [101, 999]},
    )["score"] == 0.5


def test_langsmith_evaluation_passes_graph_target_to_sdk(monkeypatch) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    workflow = LangGraphRagWorkflow(_FakeOrchestrator(), memory_enabled=False)
    captured = {}

    def fake_evaluate(target, **kwargs):
        captured.update(kwargs)
        captured["output"] = target(
            {
                "message": "제주 2일 여행",
                "selected_options": {"duration_days": 2},
            }
        )
        return "experiment-result"

    result = run_langsmith_evaluation(
        workflow=workflow,
        dataset=[{"inputs": {"message": "test"}}],
        upload_results=False,
        evaluate_fn=fake_evaluate,
    )

    assert result == "experiment-result"
    assert captured["output"]["status"] == "completed"
    assert len(captured["evaluators"]) == 3
    assert captured["metadata"]["rag_engine"] == "langgraph"


def test_langsmith_upload_requires_explicit_configuration(monkeypatch) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    workflow = LangGraphRagWorkflow(_FakeOrchestrator(), memory_enabled=False)

    with pytest.raises(RuntimeError, match="LANGSMITH_TRACING"):
        run_langsmith_evaluation(
            workflow=workflow,
            dataset="dataset",
            upload_results=True,
            evaluate_fn=lambda *args, **kwargs: None,
        )
