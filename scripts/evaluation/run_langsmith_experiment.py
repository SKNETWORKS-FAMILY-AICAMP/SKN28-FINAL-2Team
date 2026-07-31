"""Create/run the LangSmith experiment for the standalone LangGraph RAG."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.common.env import load_env_file
from src.rag import (
    LangSmithEvalCase,
    create_langgraph_rag_workflow,
    create_or_update_langsmith_dataset,
    load_eval_cases,
    run_langsmith_evaluation,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        default="skn28-jeju-rag-golden",
        help="LangSmith dataset name",
    )
    parser.add_argument(
        "--cases",
        default="evals/rag/golden_cases.jsonl",
        help="local golden JSONL used with --sync",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="create/update the LangSmith dataset before evaluation",
    )
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--max-concurrency", type=int, default=1)
    args = parser.parse_args()

    root = Path.cwd()
    load_env_file(root / ".env")
    if args.sync:
        cases = load_eval_cases(root / args.cases)
        dataset_cases = [
            LangSmithEvalCase(
                inputs={
                    "message": case.message,
                    "selected_options": dict(case.selected_options),
                    "current_conditions": dict(case.current_conditions),
                    "case_id": case.case_id,
                },
                reference_outputs=dict(case.expected),
            )
            for case in cases
            if case.stage == "end_to_end"
        ]
        dataset_id = create_or_update_langsmith_dataset(
            dataset_name=args.dataset,
            cases=dataset_cases,
        )
        print(f"LangSmith dataset ready: {dataset_id}")

    workflow = create_langgraph_rag_workflow(project_root=root)
    result = run_langsmith_evaluation(
        workflow=workflow,
        dataset=args.dataset,
        num_repetitions=args.repetitions,
        max_concurrency=args.max_concurrency,
    )
    experiment_name = getattr(result, "experiment_name", None)
    print(f"LangSmith experiment complete: {experiment_name or result}")


if __name__ == "__main__":
    main()
