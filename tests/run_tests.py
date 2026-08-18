from __future__ import annotations

from datetime import UTC, datetime
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import platform
import sys
import time
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = PROJECT_ROOT / "tests"
RESULT_PATH = TEST_ROOT / "results" / "latest.json"


class JsonTestResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cases: list[dict[str, object]] = []
        self._started_at: dict[str, float] = {}

    def startTest(self, test) -> None:
        self._started_at[test.id()] = time.perf_counter()
        super().startTest(test)

    def addSuccess(self, test) -> None:
        super().addSuccess(test)
        self._record(test, "passed")

    def addFailure(self, test, err) -> None:
        super().addFailure(test, err)
        self._record(test, "failed", self._exc_info_to_string(err, test))

    def addError(self, test, err) -> None:
        super().addError(test, err)
        self._record(test, "error", self._exc_info_to_string(err, test))

    def addSkip(self, test, reason) -> None:
        super().addSkip(test, reason)
        self._record(test, "skipped", reason)

    def _record(self, test, status: str, detail: str | None = None) -> None:
        started = self._started_at.pop(test.id(), time.perf_counter())
        case = {
            "id": test.id(),
            "area": _area_for(test.id()),
            "status": status,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        }
        if detail:
            case["detail"] = detail
        self.cases.append(case)


def _area_for(test_id: str) -> str:
    for marker, area in (
        ("aihub", "AIHub pattern"),
        ("backend", "Backend API / DB schema"),
        ("condition", "Travel condition / Planner"),
        ("embeddings", "Embedding / indexer"),
        ("engine", "Itinerary engine"),
        ("llm", "LLM contract"),
        ("package", "Package recommender"),
        ("rag", "RAG service"),
    ):
        if marker in test_id.lower():
            return area
    return "Other"


def _area_summary(cases: list[dict[str, object]]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for case in cases:
        area = str(case["area"])
        status = str(case["status"])
        counts = summary.setdefault(
            area,
            {"total": 0, "passed": 0, "failed": 0, "error": 0, "skipped": 0},
        )
        counts["total"] += 1
        counts[status] += 1
    return summary


def _findings(cases: list[dict[str, object]]) -> list[str]:
    failed_ids = {
        str(case["id"])
        for case in cases
        if case["status"] in {"failed", "error"}
    }
    findings = []
    if any("generation_rejects" in test_id for test_id in failed_ids):
        findings.append("LLM 일정 결과에서 후보 외 content_id와 중복 content_id를 차단하지 않습니다.")
    if any("revision_rejects" in test_id for test_id in failed_ids):
        findings.append("LLM 일정 수정 결과에서 변경 대상이 아닌 슬롯의 보존을 검증하지 않습니다.")
    if any("schema_satisfies" in test_id for test_id in failed_ids):
        findings.append("현재 travel_packages DB 스키마에 애플리케이션이 사용하는 match_profile 컬럼이 없습니다.")
    if any("rejects_blank_preferences" in test_id for test_id in failed_ids):
        findings.append("TravelCondition이 빈 preferred_visit_types를 허용합니다.")
    return findings


def main() -> int:
    started = time.perf_counter()
    suite = unittest.defaultTestLoader.discover(
        str(TEST_ROOT),
        pattern="test_*.py",
        top_level_dir=str(PROJECT_ROOT),
    )
    runner = unittest.TextTestRunner(verbosity=2, resultclass=JsonTestResult)
    with redirect_stdout(StringIO()):
        result: JsonTestResult = runner.run(suite)

    counts = {
        "total": result.testsRun,
        "passed": sum(case["status"] == "passed" for case in result.cases),
        "failed": len(result.failures),
        "error": len(result.errors),
        "skipped": len(result.skipped),
    }
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "passed" if result.wasSuccessful() else "failed",
        "scope": {
            "included": [
                "deterministic unit tests",
                "mock-based service contract tests",
                "read-only live MySQL schema checks when enabled",
                "real AIHub DB integration check when enabled",
            ],
            "excluded": [
                "labeled RAG relevance evaluation",
                "human-rated LLM itinerary quality evaluation",
                "paid live OpenAI response quality evaluation",
                "frontend browser end-to-end evaluation",
                "load and performance evaluation",
            ],
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "duration_seconds": round(time.perf_counter() - started, 3),
        "summary": counts,
        "pass_rate_percent": round(counts["passed"] / counts["total"] * 100, 2),
        "areas": _area_summary(result.cases),
        "findings": _findings(result.cases),
        "cases": result.cases,
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"JSON result: {RESULT_PATH}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
