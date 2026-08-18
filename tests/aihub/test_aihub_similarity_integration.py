from __future__ import annotations

import json
import os
from pathlib import Path
import unittest
from typing import Any, Sequence

from src.aihub.similarity import (
    AIHubPatternConfig,
    AIHubPatternService,
    AIHubSimilarityRepository,
    LocalTransport,
    Pace,
    PartyType,
    TravelCondition,
    TripProfile,
    VisitPreference,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INTEGRATION_ENV = "RUN_AIHUB_DB_INTEGRATION"


@unittest.skipUnless(
    os.getenv(INTEGRATION_ENV) == "1",
    f"set {INTEGRATION_ENV}=1 to query the real AIHub MySQL database",
)
class AIHubSimilarityIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _load_env_file(PROJECT_ROOT / ".env")
        repository = RecordingPatternRepository(
            AIHubSimilarityRepository(_mysql_config_from_env())
        )
        cls.repository = repository
        cls.service = AIHubPatternService(
            repository,
            AIHubPatternConfig(top_k=1, min_usable_visits=3),
        )

    def test_real_db_returns_llm_route_template(self) -> None:
        condition = TravelCondition(
            duration_days=3,
            party_type=PartyType.NON_FAMILY_TWO,
            local_transport=LocalTransport.RENTAL_CAR,
            preferred_visit_types=(
                VisitPreference.NATURE,
                VisitPreference.FOOD_CAFE,
            ),
            companion_count=1,
            purpose_codes=("7",),
            pace=Pace.BALANCED,
            entry_point="제주국제공항",
        )

        context = self.service.build_llm_context(condition)

        patterns = context["reference_trip_patterns"]
        self.assertEqual(len(patterns), 1, "matching AIHub trip was not found")
        pattern = patterns[0]
        self.assertGreater(pattern["match_score"], 0)
        self.assertTrue(pattern["days"], "the matched trip has no route days")
        self.assertTrue(
            any(day["slot_count"] > 0 for day in pattern["days"]),
            "the matched trip has no usable itinerary slots",
        )
        self.assertTrue(
            any(day["region"] is not None for day in pattern["days"]),
            "the matched trip has no usable coordinates",
        )
        self.assertEqual(
            context["context_policy"]["aihub_tourapi_mapping"],
            "ignored",
        )

        route_rows = self.repository.route_rows
        self.assertTrue(route_rows, "the matched trip has no raw route rows")
        for field in ("place_name", "road_address", "lot_address"):
            self.assertTrue(
                all(field in row for row in route_rows),
                f"raw route rows do not contain {field}",
            )
        self.assertTrue(
            any(row["place_name"] for row in route_rows),
            "raw route rows contain no place names",
        )
        self.assertTrue(
            any(
                row["road_address"] or row["lot_address"]
                for row in route_rows
            ),
            "raw route rows contain no addresses",
        )

        serialized = json.dumps(context, ensure_ascii=False)
        for excluded_field in (
            "traveler_id",
            "place_name",
            "road_address",
            "lot_address",
            "visit_area_nm",
            "road_nm_addr",
            "lotno_addr",
            "tourapi_content_id",
        ):
            self.assertNotIn(excluded_field, serialized)

        print("\n=== REAL AIHUB DB RESULT (LLM route template) ===")
        print(json.dumps(context, ensure_ascii=False, indent=2))
        print("\n=== RAW SQL ROUTE SAMPLE (not sent to LLM) ===")
        print(
            json.dumps(
                [
                    {
                        field: row.get(field)
                        for field in (
                            "day_no",
                            "visit_order",
                            "place_name",
                            "road_address",
                            "lot_address",
                        )
                    }
                    for row in route_rows[:3]
                ],
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )


class RecordingPatternRepository:
    def __init__(self, delegate: AIHubSimilarityRepository) -> None:
        self.delegate = delegate
        self.route_rows: list[dict[str, Any]] = []

    def fetch_trip_profiles(
        self,
        *,
        min_usable_visits: int,
    ) -> list[TripProfile]:
        return self.delegate.fetch_trip_profiles(
            min_usable_visits=min_usable_visits
        )

    def fetch_trip_routes(
        self,
        travel_ids: Sequence[str],
    ) -> list[dict[str, Any]]:
        self.route_rows = self.delegate.fetch_trip_routes(travel_ids)
        return self.route_rows


def _load_env_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"environment file not found: {path}")
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(name, value)


def _mysql_config_from_env() -> dict[str, object]:
    required_names = (
        "MYSQL_HOST",
        "MYSQL_USER",
        "MYSQL_PASSWORD",
    )
    missing = [name for name in required_names if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            "missing MySQL environment variables: " + ", ".join(missing)
        )
    return {
        "host": os.environ["MYSQL_HOST"],
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.environ["MYSQL_USER"],
        "password": os.environ["MYSQL_PASSWORD"],
        "database": os.getenv(
            "AIHUB_MYSQL_DATABASE",
            "tour_recommender_aihub",
        ),
        "connection_timeout": int(
            os.getenv("MYSQL_CONNECT_TIMEOUT", "10")
        ),
    }


if __name__ == "__main__":
    unittest.main(verbosity=2)
