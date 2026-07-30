"""Run the local golden-set evaluation for condition extraction and RAG."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import time
from typing import Any, Mapping

from src.rag import (
    EvalCase,
    OpenAIItineraryJudge,
    build_report,
    create_rag_orchestrator,
    evaluate_case,
    load_eval_cases,
    report_as_markdown,
)


DEFAULT_DATASET = Path("evals/rag/golden_cases.jsonl")
DEFAULT_OUTPUT_DIRECTORY = Path("artifacts/rag_evaluation")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the RAG with deterministic task metrics and an optional "
            "OpenAI pass/fail judge."
        )
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument(
        "--offline-results",
        type=Path,
        help=(
            "JSONL containing case_id and result. When supplied, no RAG or "
            "OpenAI generation calls are made."
        ),
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument(
        "--case-id",
        action="append",
        help="Run only the named case. Repeat this option to select several cases.",
    )
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument(
        "--llm-judge",
        action="store_true",
        help="Add the optional OpenAI pass/fail judge (incurs API cost).",
    )
    parser.add_argument("--judge-model")
    parser.add_argument(
        "--pass-rate",
        type=float,
        default=0.80,
        help="Minimum fraction of cases that must pass.",
    )
    parser.add_argument(
        "--case-score",
        type=float,
        default=0.80,
        help="Minimum average metric score for an individual case.",
    )
    parser.add_argument(
        "--include-results",
        action="store_true",
        help="Store raw RAG results in the JSON artifact.",
    )
    parser.add_argument(
        "--no-fail",
        action="store_true",
        help="Always exit zero; useful while establishing a baseline.",
    )
    return parser.parse_args()


def _validate_args(args: argparse.Namespace) -> None:
    if args.repeat <= 0:
        raise ValueError("--repeat must be positive")
    if args.max_cases is not None and args.max_cases <= 0:
        raise ValueError("--max-cases must be positive")
    for name in ("pass_rate", "case_score"):
        value = float(getattr(args, name))
        if not 0 <= value <= 1:
            raise ValueError(f"--{name.replace('_', '-')} must be between 0 and 1")


def _load_offline_results(path: Path) -> dict[str, list[Mapping[str, Any]]]:
    results: dict[str, list[Mapping[str, Any]]] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if not isinstance(payload, Mapping):
            raise ValueError(f"{path}:{line_number}: row must be an object")
        case_id = str(payload.get("case_id") or "").strip()
        result = payload.get("result")
        if not case_id or not isinstance(result, Mapping):
            raise ValueError(
                f"{path}:{line_number}: case_id and result object are required"
            )
        results.setdefault(case_id, []).append(dict(result))
    return results


def _condition_result(orchestrator: Any, case: EvalCase) -> dict[str, Any]:
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
        "status": "conditions_ready" if value.ready else "clarification_required",
        **value.to_dict(),
    }


def _run_live_case(orchestrator: Any, case: EvalCase) -> dict[str, Any]:
    if case.stage == "conditions":
        return _condition_result(orchestrator, case)
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
            {"calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        )
        bucket["calls"] += 1
        for name in ("input_tokens", "output_tokens", "total_tokens"):
            bucket[name] += int(record.get(name) or 0)
    return {
        "calls": len(records),
        "input_tokens": sum(int(item.get("input_tokens") or 0) for item in records),
        "output_tokens": sum(int(item.get("output_tokens") or 0) for item in records),
        "total_tokens": sum(int(item.get("total_tokens") or 0) for item in records),
        "by_stage": by_stage,
    }


def main() -> int:
    args = parse_args()
    _validate_args(args)
    cases = load_eval_cases(args.dataset)
    if args.case_id:
        requested = set(args.case_id)
        cases = [case for case in cases if case.case_id in requested]
        missing = requested - {case.case_id for case in cases}
        if missing:
            raise ValueError(
                "unknown --case-id values: " + ", ".join(sorted(missing))
            )
    if args.max_cases:
        cases = cases[: args.max_cases]
    offline = (
        _load_offline_results(args.offline_results)
        if args.offline_results
        else None
    )
    orchestrator = (
        None
        if offline is not None
        else create_rag_orchestrator(project_root=Path.cwd())
    )
    judge = (
        OpenAIItineraryJudge(model=args.judge_model)
        if args.llm_judge
        else None
    )
    evaluations = []
    raw_results: list[dict[str, Any]] = []
    all_usage: list[dict[str, Any]] = []
    for repeat_index in range(args.repeat):
        for case in cases:
            evaluation_case = (
                case
                if args.repeat == 1
                else EvalCase(
                    **{
                        **case.__dict__,
                        "case_id": f"{case.case_id}#{repeat_index + 1}",
                    }
                )
            )
            started = time.perf_counter()
            if offline is not None:
                candidates = offline.get(case.case_id) or []
                if not candidates:
                    raise ValueError(
                        f"offline result is missing for case: {case.case_id}"
                    )
                result = dict(
                    candidates[
                        min(repeat_index, len(candidates) - 1)
                    ]
                )
            else:
                result = _run_live_case(orchestrator, case)
            latency_ms = (time.perf_counter() - started) * 1000
            if orchestrator is not None:
                all_usage.extend(_drain_usage(orchestrator))
            evaluation = evaluate_case(
                evaluation_case,
                result,
                latency_ms=latency_ms,
                judge=judge,
                pass_threshold=args.case_score,
            )
            evaluations.append(evaluation)
            if args.include_results:
                raw_results.append(
                    {
                        "case_id": evaluation_case.case_id,
                        "result": result,
                    }
                )
            print(
                f"[{'PASS' if evaluation.passed else 'FAIL'}] "
                f"{evaluation.case_id}: {evaluation.score:.3f} "
                f"({evaluation.result_status})",
                flush=True,
            )

    report = build_report(evaluations, pass_threshold=args.pass_rate)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / f"rag-eval-{timestamp}.json"
    markdown_path = args.output_dir / f"rag-eval-{timestamp}.md"
    artifact = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "dataset": str(args.dataset),
        "repeat": args.repeat,
        "llm_judge": bool(args.llm_judge),
        "usage": _usage_summary(all_usage),
        "report": report.to_dict(),
    }
    if args.include_results:
        artifact["raw_results"] = raw_results
    json_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(report_as_markdown(report), encoding="utf-8")
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0 if report.passed or args.no_fail else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"RAG evaluation failed: {exc}", file=sys.stderr)
        raise
