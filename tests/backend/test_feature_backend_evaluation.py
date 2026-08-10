from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient

from backend.evaluation_app import create_app
from backend.services.evaluation_jobs import FeatureBackendEvaluationManager, RetrievalEvalCase


@dataclass
class _Place:
    content_id: int
    title: str
    content_type_id: int = 12
    similarity_score: float = 0.9

    def to_dict(self):
        return {
            "content_id": self.content_id,
            "title": self.title,
            "content_type_id": self.content_type_id,
            "similarity_score": self.similarity_score,
        }


@dataclass
class _Response:
    places: tuple[_Place, ...]


class _FakeService:
    def search_places(self, query, *, filters, top_k):
        return _Response(
            places=(
                _Place(127514, "한라수목원", 12, 0.95),
                _Place(100002, "제주 자연 산책", 12, 0.85),
            )
        )


def test_health_and_cases_endpoints():
    root = Path(__file__).resolve().parents[2]
    app = create_app(root)
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["service"] == "tamna-plan-feature-backend-rag-evaluation"
        cases = client.get("/api/evaluation/cases")
        assert cases.status_code == 200
        assert cases.json()["count"] >= 1


def test_retrieval_metrics_use_feature_backend_response(tmp_path):
    manager = FeatureBackendEvaluationManager(tmp_path, service_factory=lambda _: _FakeService())
    try:
        case = RetrievalEvalCase(
            case_id="unit_halla",
            stage="retrieval",
            message="한라수목원",
            query="한라수목원 자연 산책",
            top_k=8,
            filters={"content_type_ids": [12]},
            expected={
                "required_content_ids": [127514],
                "min_results": 1,
                "allowed_content_type_ids": [12],
                "max_latency_ms": 20000,
            },
        )
        evaluation, raw = manager._evaluate_case(
            _FakeService(),
            case,
            display_id=case.case_id,
            pass_threshold=0.8,
        )
        assert evaluation["passed"] is True
        assert raw["status"] == "completed"
        assert raw["places"][0]["content_id"] == 127514
        metrics = {item["name"]: item for item in evaluation["metrics"]}
        assert metrics["required_place_recall"]["value"] == 1.0
        assert metrics["content_type_filter_compliance"]["value"] == 1.0
    finally:
        manager.shutdown()
