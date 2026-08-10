from __future__ import annotations

from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from statistics import mean
from threading import RLock
import time
from typing import Any, Callable, Mapping
from uuid import uuid4

from backend.json_utils import to_jsonable
from src.rag.api import create_place_search_service
from src.rag.models import PlaceSearchFilters


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


@dataclass(frozen=True)
class RetrievalEvalCase:
    case_id: str
    stage: str
    message: str
    query: str
    top_k: int
    filters: dict[str, Any]
    expected: dict[str, Any]
    tags: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RetrievalEvalCase":
        case_id = str(value.get("id") or value.get("case_id") or "").strip()
        query = str(value.get("query") or value.get("message") or "").strip()
        if not case_id:
            raise ValueError("evaluation case id is required")
        if not query:
            raise ValueError(f"evaluation case query is required: {case_id}")
        return cls(
            case_id=case_id,
            stage=str(value.get("stage") or "retrieval"),
            message=str(value.get("message") or query),
            query=query,
            top_k=max(1, int(value.get("top_k") or 8)),
            filters=dict(value.get("filters") or {}),
            expected=dict(value.get("expected") or {}),
            tags=tuple(str(item) for item in value.get("tags") or ()),
        )

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.case_id,
            "stage": self.stage,
            "message": self.message,
            "query": self.query,
            "top_k": self.top_k,
            "filters": self.filters,
            "expected": self.expected,
            "tags": list(self.tags),
        }


@dataclass
class EvaluationJob:
    job_id: str
    request: dict[str, Any]
    output_dir: Path
    total_cases: int
    status: str = "queued"
    created_at: str = field(default_factory=_now)
    started_at: str | None = None
    finished_at: str | None = None
    completed_cases: int = 0
    evaluation_passed: bool | None = None
    json_path: Path | None = None
    markdown_path: Path | None = None
    error: str | None = None
    logs: deque[str] = field(default_factory=lambda: deque(maxlen=500))
    case_progress: list[dict[str, Any]] = field(default_factory=list)

    @property
    def progress(self) -> float:
        return min(1.0, self.completed_cases / self.total_cases) if self.total_cases else 0.0

    @property
    def report_available(self) -> bool:
        return bool(self.json_path and self.json_path.exists())

    def to_dict(self, *, include_logs: bool = True) -> dict[str, Any]:
        payload = {
            "job_id": self.job_id,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "completed_cases": self.completed_cases,
            "total_cases": self.total_cases,
            "progress": round(self.progress, 6),
            "evaluation_passed": self.evaluation_passed,
            "report_available": self.report_available,
            "error": self.error,
            "case_progress": list(self.case_progress),
        }
        if include_logs:
            payload["logs"] = list(self.logs)
        return payload


class FeatureBackendEvaluationManager:
    """Run deterministic retrieval evaluation against feature/backend PlaceSearchService."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        max_workers: int = 1,
        service_factory: Callable[[Path], Any] | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.dataset_path = self.project_root / "evals/feature_backend/golden_cases.jsonl"
        self.report_root = self.project_root / "artifacts/rag_evaluation"
        self.api_report_root = self.report_root / "api_jobs"
        self._jobs: dict[str, EvaluationJob] = {}
        self._lock = RLock()
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, max_workers),
            thread_name_prefix="feature-backend-rag-evaluation",
        )
        self._service_factory = service_factory or (lambda root: create_place_search_service(root))

    def _load_cases(self) -> list[RetrievalEvalCase]:
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"evaluation dataset not found: {self.dataset_path}")
        cases: list[RetrievalEvalCase] = []
        for line_number, raw_line in enumerate(
            self.dataset_path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{self.dataset_path}:{line_number}: {exc}") from exc
            cases.append(RetrievalEvalCase.from_mapping(payload))
        if not cases:
            raise ValueError("evaluation dataset is empty")
        return cases

    def list_cases(self) -> list[dict[str, Any]]:
        return [case.public_dict() for case in self._load_cases()]

    def submit(self, request: Mapping[str, Any]) -> EvaluationJob:
        cases = self._select_cases(request)
        repeat = int(request.get("repeat") or 1)
        total_cases = len(cases) * repeat
        if total_cases <= 0:
            raise ValueError("Select at least one evaluation case")
        job_id = f"eval-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"
        job = EvaluationJob(
            job_id=job_id,
            request=to_jsonable(dict(request)),
            output_dir=self.api_report_root / job_id,
            total_cases=total_cases,
        )
        with self._lock:
            self._jobs[job_id] = job
        self._executor.submit(self._run_job, job, cases, repeat)
        return job

    def _select_cases(self, request: Mapping[str, Any]) -> list[RetrievalEvalCase]:
        cases = self._load_cases()
        requested = [str(item) for item in request.get("case_ids") or ()]
        if requested:
            by_id = {case.case_id: case for case in cases}
            unknown = sorted(set(requested) - set(by_id))
            if unknown:
                raise ValueError("Unknown evaluation case IDs: " + ", ".join(unknown))
            cases = [by_id[case_id] for case_id in requested]
        max_cases = request.get("max_cases")
        if max_cases is not None:
            cases = cases[: int(max_cases)]
        return cases

    def get(self, job_id: str) -> EvaluationJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda item: item.created_at, reverse=True)
            return [job.to_dict(include_logs=False) for job in jobs]

    def read_job_artifact(self, job_id: str) -> dict[str, Any]:
        job = self.get(job_id)
        if job is None:
            raise KeyError(job_id)
        if not job.json_path or not job.json_path.exists():
            raise FileNotFoundError("Evaluation report is not ready")
        return json.loads(job.json_path.read_text(encoding="utf-8"))

    def job_file(self, job_id: str, file_format: str) -> Path:
        job = self.get(job_id)
        if job is None:
            raise KeyError(job_id)
        path = job.json_path if file_format == "json" else job.markdown_path
        if path is None or not path.exists():
            raise FileNotFoundError("Evaluation report is not ready")
        return path

    def list_reports(self) -> list[dict[str, Any]]:
        if not self.report_root.exists():
            return []
        reports: list[dict[str, Any]] = []
        for path in self.report_root.rglob("rag-eval-*.json"):
            try:
                artifact = json.loads(path.read_text(encoding="utf-8"))
                report = artifact.get("report") or {}
            except (OSError, json.JSONDecodeError):
                continue
            reports.append(
                {
                    "path": path.relative_to(self.report_root).as_posix(),
                    "generated_at": artifact.get("generated_at"),
                    "passed": report.get("passed"),
                    "case_count": report.get("case_count"),
                    "pass_rate": report.get("pass_rate"),
                    "average_score": report.get("average_score"),
                }
            )
        return sorted(reports, key=lambda item: str(item.get("generated_at") or ""), reverse=True)

    def resolve_report_path(self, relative_path: str) -> Path:
        target = (self.report_root / relative_path).resolve()
        report_root = self.report_root.resolve()
        if target != report_root and report_root not in target.parents:
            raise ValueError("Invalid report path")
        if target.suffix.lower() != ".json" or not target.exists():
            raise FileNotFoundError(relative_path)
        return target

    def _run_job(
        self,
        job: EvaluationJob,
        cases: list[RetrievalEvalCase],
        repeat: int,
    ) -> None:
        job.status = "running"
        job.started_at = _now()
        job.output_dir.mkdir(parents=True, exist_ok=True)
        case_score_threshold = float(job.request.get("case_score", 0.8))
        pass_rate_threshold = float(job.request.get("pass_rate", 0.8))
        include_results = bool(job.request.get("include_results", True))
        if job.request.get("llm_judge"):
            job.logs.append("[NOTICE] LLM Judge is not used by the feature/backend retrieval evaluator.")

        evaluations: list[dict[str, Any]] = []
        raw_results: list[dict[str, Any]] = []
        try:
            job.logs.append("Initializing feature/backend PlaceSearchService...")
            service = self._service_factory(self.project_root)
            for repeat_index in range(repeat):
                for case in cases:
                    display_id = case.case_id if repeat == 1 else f"{case.case_id}#{repeat_index + 1}"
                    evaluation, raw_result = self._evaluate_case(
                        service,
                        case,
                        display_id=display_id,
                        pass_threshold=case_score_threshold,
                    )
                    evaluations.append(evaluation)
                    if include_results:
                        raw_results.append({"case_id": display_id, "result": raw_result})
                    job.completed_cases += 1
                    job.case_progress.append(
                        {
                            "case_id": display_id,
                            "passed": evaluation["passed"],
                            "score": evaluation["score"],
                            "status": evaluation["result_status"],
                        }
                    )
                    status_text = "PASS" if evaluation["passed"] else "FAIL"
                    job.logs.append(
                        f"[{status_text}] {display_id}: {evaluation['score']:.3f} "
                        f"({evaluation['result_status']})"
                    )

            report = _build_report(evaluations, pass_rate_threshold)
            artifact: dict[str, Any] = {
                "generated_at": _now(),
                "dataset": str(self.dataset_path),
                "rag_source": "origin/feature/backend",
                "evaluator": "feature_backend_retrieval_v1",
                "repeat": repeat,
                "llm_judge": False,
                "report": report,
            }
            if include_results:
                artifact["raw_results"] = raw_results
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            job.json_path = job.output_dir / f"rag-eval-{timestamp}.json"
            job.markdown_path = job.output_dir / f"rag-eval-{timestamp}.md"
            job.json_path.write_text(
                json.dumps(to_jsonable(artifact), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            job.markdown_path.write_text(_report_as_markdown(report), encoding="utf-8")
            job.evaluation_passed = bool(report["passed"])
            job.status = "completed"
            job.logs.append(f"JSON: {job.json_path.relative_to(self.project_root)}")
            job.logs.append(f"Markdown: {job.markdown_path.relative_to(self.project_root)}")
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            job.logs.append(f"Backend evaluation error: {exc}")
        finally:
            job.finished_at = _now()

    def _evaluate_case(
        self,
        service: Any,
        case: RetrievalEvalCase,
        *,
        display_id: str,
        pass_threshold: float,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        started = time.perf_counter()
        error: str | None = None
        places: list[dict[str, Any]] = []
        try:
            filters = PlaceSearchFilters(**case.filters)
            response = service.search_places(case.query, filters=filters, top_k=case.top_k)
            places = [item.to_dict() if hasattr(item, "to_dict") else to_jsonable(item) for item in response.places]
            result_status = "completed"
        except Exception as exc:
            error = str(exc)
            result_status = "failed"
        latency_ms = (time.perf_counter() - started) * 1000

        metrics: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        metrics.append(_metric("execution_success", 1.0 if error is None else 0.0, 1.0, gate=True, details={"error": error}))

        expected = case.expected
        min_results = int(expected.get("min_results") or 1)
        result_count_score = min(1.0, len(places) / max(1, min_results))
        metrics.append(_metric("min_results", result_count_score, 1.0, gate=True, details={"expected_min": min_results, "actual": len(places)}))

        required_ids = {int(item) for item in expected.get("required_content_ids") or ()}
        returned_ids = [int(item.get("content_id")) for item in places if item.get("content_id") is not None]
        returned_set = set(returned_ids)
        if required_ids:
            recall = len(required_ids & returned_set) / len(required_ids)
            metrics.append(_metric("required_place_recall", recall, 1.0, gate=True, details={"required": sorted(required_ids), "returned": returned_ids}))

        allowed_types = {int(item) for item in expected.get("allowed_content_type_ids") or ()}
        if allowed_types:
            matched = sum(1 for item in places if item.get("content_type_id") in allowed_types)
            compliance = matched / len(places) if places else 0.0
            metrics.append(_metric("content_type_filter_compliance", compliance, 1.0, gate=True, details={"allowed": sorted(allowed_types), "actual": [item.get("content_type_id") for item in places]}))

        unique_ratio = len(set(returned_ids)) / len(returned_ids) if returned_ids else 0.0
        metrics.append(_metric("unique_place_ratio", unique_ratio, 1.0, gate=True, details={"content_ids": returned_ids}))

        grounding_count = sum(
            1
            for item in places
            if item.get("content_id") is not None and str(item.get("title") or "").strip()
        )
        grounding = grounding_count / len(places) if places else 0.0
        metrics.append(_metric("mysql_grounding", grounding, 1.0, gate=True, details={"grounded": grounding_count, "total": len(places)}))

        similarity_values = [item.get("similarity_score") for item in places]
        similarity_coverage = sum(value is not None for value in similarity_values) / len(places) if places else 0.0
        metrics.append(_metric("similarity_score_coverage", similarity_coverage, 1.0, gate=False, details={"scores": similarity_values}))

        finite_scores = [float(value) for value in similarity_values if value is not None]
        descending = all(left >= right for left, right in zip(finite_scores, finite_scores[1:])) if finite_scores else False
        metrics.append(_metric("rank_order_accuracy", 1.0 if descending else 0.0, 1.0, gate=False, details={"scores": finite_scores}))

        max_latency_ms = float(expected.get("max_latency_ms") or 20000)
        metrics.append(_metric("latency_within_limit", 1.0 if latency_ms <= max_latency_ms else 0.0, 1.0, gate=False, details={"latency_ms": round(latency_ms, 3), "limit_ms": max_latency_ms}))

        for metric in metrics:
            if not metric["passed"]:
                warnings.append(
                    {
                        "code": metric["name"],
                        "message": _warning_message(metric),
                    }
                )
        score = mean(metric["value"] for metric in metrics) if metrics else 0.0
        gate_failed = any(metric["gate"] and not metric["passed"] for metric in metrics)
        passed = bool(metrics) and score >= pass_threshold and not gate_failed
        failure_tags = [metric["name"] for metric in metrics if not metric["passed"]]

        evaluation = {
            "case_id": display_id,
            "passed": passed,
            "score": round(score, 6),
            "metrics": metrics,
            "failure_tags": failure_tags,
            "result_status": result_status,
            "latency_ms": round(latency_ms, 3),
            "judge": None,
        }
        raw_result = {
            "status": result_status,
            "query": case.query,
            "filters": case.filters,
            "top_k": case.top_k,
            "places": places,
            "error": error,
            "validation": {"warnings": warnings},
        }
        return evaluation, raw_result

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=False)


def _metric(
    name: str,
    value: float,
    threshold: float,
    *,
    gate: bool,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = max(0.0, min(1.0, float(value)))
    return {
        "name": name,
        "value": round(normalized, 6),
        "passed": normalized >= threshold,
        "threshold": threshold,
        "gate": gate,
        "details": to_jsonable(dict(details or {})),
    }


def _warning_message(metric: Mapping[str, Any]) -> str:
    details = metric.get("details") or {}
    if metric.get("name") == "execution_success":
        return f"RAG 검색 실행에 실패했습니다: {details.get('error') or 'unknown error'}"
    if metric.get("name") == "min_results":
        return f"검색 결과가 부족합니다. 기대 {details.get('expected_min')}개, 실제 {details.get('actual')}개"
    if metric.get("name") == "required_place_recall":
        return "필수 장소가 검색 상위 결과에 포함되지 않았습니다."
    if metric.get("name") == "content_type_filter_compliance":
        return "검색 결과 중 콘텐츠 유형 필터를 위반한 장소가 있습니다."
    if metric.get("name") == "unique_place_ratio":
        return "검색 결과에 중복 장소가 있습니다."
    if metric.get("name") == "mysql_grounding":
        return "MySQL 원본 정보로 복원되지 않은 검색 결과가 있습니다."
    if metric.get("name") == "similarity_score_coverage":
        return "일부 결과에 Chroma 유사도 점수가 없습니다."
    if metric.get("name") == "rank_order_accuracy":
        return "검색 결과가 유사도 점수 내림차순으로 정렬되지 않았습니다."
    if metric.get("name") == "latency_within_limit":
        return "검색 응답 시간이 기준을 초과했습니다."
    return f"평가 지표 {metric.get('name')}가 기준을 통과하지 못했습니다."


def _build_report(evaluations: list[dict[str, Any]], pass_threshold: float) -> dict[str, Any]:
    case_count = len(evaluations)
    pass_rate = mean(1.0 if item["passed"] else 0.0 for item in evaluations) if evaluations else 0.0
    average_score = mean(float(item["score"]) for item in evaluations) if evaluations else 0.0
    grouped: dict[str, list[float]] = {}
    failure_counts: dict[str, int] = {}
    for evaluation in evaluations:
        for metric in evaluation.get("metrics") or ():
            grouped.setdefault(str(metric["name"]), []).append(float(metric["value"]))
        for tag in evaluation.get("failure_tags") or ():
            failure_counts[str(tag)] = failure_counts.get(str(tag), 0) + 1
    metric_averages = {name: round(mean(values), 6) for name, values in sorted(grouped.items())}
    return {
        "passed": bool(evaluations) and pass_rate >= pass_threshold,
        "case_count": case_count,
        "pass_threshold": pass_threshold,
        "pass_rate": round(pass_rate, 6),
        "average_score": round(average_score, 6),
        "metric_averages": metric_averages,
        "failure_counts": dict(sorted(failure_counts.items())),
        "cases": evaluations,
    }


def _report_as_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# feature/backend RAG 검색 평가 결과",
        "",
        f"- 전체 통과: {'예' if report.get('passed') else '아니오'}",
        f"- 케이스 수: {report.get('case_count', 0)}",
        f"- 통과율: {float(report.get('pass_rate') or 0) * 100:.1f}%",
        f"- 평균 점수: {float(report.get('average_score') or 0):.3f}",
        "",
        "## 지표 평균",
        "",
        "| 지표 | 평균 |",
        "|---|---:|",
    ]
    for name, value in (report.get("metric_averages") or {}).items():
        lines.append(f"| `{name}` | {float(value):.3f} |")
    lines.extend(["", "## 케이스", "", "| ID | 통과 | 점수 | 상태 | 실패 태그 |", "|---|---:|---:|---|---|"])
    for item in report.get("cases") or ():
        tags = ", ".join(item.get("failure_tags") or ())
        lines.append(
            f"| `{item.get('case_id')}` | {'PASS' if item.get('passed') else 'FAIL'} | "
            f"{float(item.get('score') or 0):.3f} | `{item.get('result_status')}` | {tags} |"
        )
    lines.append("")
    return "\n".join(lines)
