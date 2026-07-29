"""Opt-in tests against the real local configuration and external services.

Run route-provider verification:
    $env:RUN_RAG_LIVE_E2E="1"
    python -m pytest tests/rag/test_live_e2e.py -q

Run the full MySQL + Chroma + OpenAI orchestration smoke test too:
    $env:RUN_RAG_FULL_LIVE_E2E="1"
    python -m pytest tests/rag/test_live_e2e.py -q
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.common.env import load_env_file
from src.rag import (
    create_rag_orchestrator,
    create_route_metrics_provider_from_env,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_env_file(PROJECT_ROOT / ".env")


@pytest.mark.skipif(
    os.getenv("RUN_RAG_LIVE_E2E") != "1",
    reason="set RUN_RAG_LIVE_E2E=1 to call the configured route API",
)
def test_configured_route_provider_returns_a_verified_jeju_road_route() -> None:
    provider = create_route_metrics_provider_from_env()
    result = provider.estimate(
        (33.5104, 126.4913),  # 제주국제공항
        (33.4698, 126.4930),  # 한라수목원 인근
        transport="rental_car",
    )

    assert result.verified, (
        "The configured road provider was unavailable and the pipeline "
        "fell back to a straight-line estimate."
    )
    assert result.provider in {"kakao_mobility", "google_routes"}
    assert result.distance_km > 0
    assert result.duration_minutes > 0


@pytest.mark.skipif(
    os.getenv("RUN_RAG_FULL_LIVE_E2E") != "1",
    reason=(
        "set RUN_RAG_FULL_LIVE_E2E=1 to call MySQL, Chroma, and OpenAI"
    ),
)
def test_full_local_rag_pipeline_smoke() -> None:
    rag = create_rag_orchestrator(project_root=PROJECT_ROOT)
    result = rag.run(
        selected_options={
            "region": "제주",
            "start_date": "2026-08-18",
            "end_date": "2026-08-18",
            "duration_days": 1,
            "party_type": "non_family_two",
            "local_transport": "rental_car",
            "preferred_visit_types": ["nature", "culture"],
            "entry_point": "제주국제공항",
            "entry_latitude": 33.5104,
            "entry_longitude": 126.4913,
            "exit_point": "제주국제공항",
            "exit_latitude": 33.5104,
            "exit_longitude": 126.4913,
        }
    )

    assert result.get("status")
    assert result.get("conditions", {}).get("duration_days") == 1
    assert "meta" in result or result["status"] == "clarification_required"
