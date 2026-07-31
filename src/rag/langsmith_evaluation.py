"""LangSmith dataset and experiment adapters for the RAG workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from .langgraph_workflow import LangGraphRagWorkflow
from .langsmith_observability import langsmith_status


@dataclass(frozen=True)
class LangSmithEvalCase:
    inputs: Mapping[str, Any]
    reference_outputs: Mapping[str, Any]

    def to_example(self) -> dict[str, Any]:
        return {
            "inputs": dict(self.inputs),
            "outputs": dict(self.reference_outputs),
        }


def create_or_update_langsmith_dataset(
    *,
    dataset_name: str,
    cases: Sequence[LangSmithEvalCase],
    description: str = "SKN28 제주 여행 RAG 회귀 평가 데이터",
    client: Any | None = None,
) -> str:
    """Create a LangSmith dataset and upsert examples without exposing a key."""

    if not dataset_name.strip():
        raise ValueError("dataset_name must not be blank")
    if not cases:
        raise ValueError("cases must not be empty")
    if client is None:
        from langsmith import Client

        client = Client()
    try:
        dataset = client.read_dataset(dataset_name=dataset_name)
    except Exception:
        dataset = client.create_dataset(
            dataset_name=dataset_name,
            description=description,
        )
    client.create_examples(
        dataset_id=dataset.id,
        examples=[case.to_example() for case in cases],
    )
    return str(dataset.id)


def run_langsmith_evaluation(
    *,
    workflow: LangGraphRagWorkflow,
    dataset: Any,
    experiment_prefix: str = "skn28-jeju-rag",
    num_repetitions: int = 1,
    max_concurrency: int = 1,
    upload_results: bool = True,
    evaluate_fn: Callable[..., Any] | None = None,
) -> Any:
    """Evaluate the graph using deterministic itinerary contract metrics."""

    if num_repetitions < 1:
        raise ValueError("num_repetitions must be at least 1")
    if not 1 <= max_concurrency <= 4:
        raise ValueError("max_concurrency must be between 1 and 4")
    if upload_results and not langsmith_status().enabled:
        raise RuntimeError(
            "LangSmith upload requires LANGSMITH_TRACING=true and "
            "LANGSMITH_API_KEY"
        )
    if evaluate_fn is None:
        from langsmith import evaluate

        evaluate_fn = evaluate

    def target(inputs: Mapping[str, Any]) -> dict[str, Any]:
        return workflow.run(
            message=str(inputs.get("message") or ""),
            selected_options=_mapping_or_none(
                inputs.get("selected_options")
            ),
            current_conditions=_mapping_or_none(
                inputs.get("current_conditions")
            ),
            thread_id=str(inputs.get("thread_id") or "") or None,
            trace_metadata={"evaluation": True},
        )

    return evaluate_fn(
        target,
        data=dataset,
        evaluators=[
            itinerary_completion_evaluator,
            deterministic_validation_evaluator,
            required_place_coverage_evaluator,
        ],
        metadata={
            "models": ["gpt-5-mini"],
            "prompts": ["condition-v6", "itinerary-v7", "repair-v7"],
            "tools": ["AIHub MySQL", "TourAPI Chroma/MySQL", "route APIs"],
            "rag_engine": "langgraph",
        },
        experiment_prefix=experiment_prefix,
        description=(
            "LangGraph 기반 제주 일정 RAG의 생성 완결성·결정론적 검증·"
            "필수 장소 충족률 평가"
        ),
        num_repetitions=num_repetitions,
        max_concurrency=max_concurrency,
        upload_results=upload_results,
    )


def itinerary_completion_evaluator(
    *,
    outputs: Mapping[str, Any],
    **_: Any,
) -> dict[str, Any]:
    itinerary = outputs.get("itinerary")
    completed = (
        outputs.get("status") == "completed"
        and isinstance(itinerary, Sequence)
        and not isinstance(itinerary, (str, bytes))
        and len(itinerary) > 0
    )
    return {
        "key": "itinerary_completed",
        "score": 1.0 if completed else 0.0,
        "comment": str(outputs.get("status") or "unknown"),
    }


def deterministic_validation_evaluator(
    *,
    outputs: Mapping[str, Any],
    **_: Any,
) -> dict[str, Any]:
    validation = outputs.get("validation")
    valid = (
        isinstance(validation, Mapping)
        and bool(validation.get("valid"))
    )
    return {
        "key": "deterministic_validation",
        "score": 1.0 if valid else 0.0,
        "comment": (
            "운영시간·거리·화이트리스트 검증 통과"
            if valid
            else "결정론적 검증 미통과"
        ),
    }


def required_place_coverage_evaluator(
    *,
    outputs: Mapping[str, Any],
    reference_outputs: Mapping[str, Any] | None = None,
    **_: Any,
) -> dict[str, Any]:
    expected_ids = {
        int(value)
        for value in (reference_outputs or {}).get(
            "required_content_ids",
            (),
        )
    }
    if not expected_ids:
        return {
            "key": "required_place_coverage",
            "score": 1.0,
            "comment": "평가 케이스에 필수 장소 ID 없음",
        }
    actual_ids = {
        int(item.get("content_id"))
        for item in outputs.get("itinerary") or ()
        if isinstance(item, Mapping) and item.get("content_id") is not None
    }
    coverage = len(expected_ids & actual_ids) / len(expected_ids)
    return {
        "key": "required_place_coverage",
        "score": round(coverage, 4),
        "comment": f"{len(expected_ids & actual_ids)}/{len(expected_ids)}",
    }


def _mapping_or_none(value: Any) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, Mapping) and value else None
