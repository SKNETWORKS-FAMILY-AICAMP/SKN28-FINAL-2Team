from __future__ import annotations

import os
from datetime import date
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from rest_framework.test import APIRequestFactory, force_authenticate

from apps.travel.models import Itinerary
from apps.travel.serializers import ItinerarySerializer
from apps.travel.services import _merge_schedule_into_engine_state, generate_itinerary
from apps.travel.views import ItineraryViewSet
from src.config.settings import MySQLConfig
from src.recommender.package_repository import MySQLPackageRepository
from src.storage.mysql_repository import MySQLPlaceRepository


class ItineraryGenerationReflectionTests(unittest.TestCase):
    def test_additional_request_is_accepted_as_write_only_input(self) -> None:
        serializer = ItinerarySerializer(
            data={
                "start_date": "2026-08-10",
                "end_date": "2026-08-12",
                "additional_request": "협재해변을 꼭 넣어줘",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["additional_request"],
            "협재해변을 꼭 넣어줘",
        )
        self.assertTrue(serializer.fields["additional_request"].write_only)

    @patch("apps.travel.services._save_itinerary_result")
    @patch("apps.travel.services.get_itinerary_engine")
    def test_generation_passes_additional_request_to_engine(
        self,
        mocked_get_engine,
        mocked_save_result,
    ) -> None:
        mocked_create = mocked_get_engine.return_value.create_itinerary
        mocked_create.return_value = SimpleNamespace(
            itinerary={"days": []},
            slots=[],
            to_dict=lambda: {"itinerary": {"days": []}},
        )
        itinerary = SimpleNamespace(
            duration_label="2박 3일",
            companion_type="family",
            age_group="30s",
            style="healing",
            get_style_display=lambda: "힐링여행",
            get_companion_type_display=lambda: "가족",
            title="",
            engine_state=None,
            save=lambda **_kwargs: None,
        )

        generate_itinerary.__wrapped__(
            itinerary,
            additional_request="협재해변을 꼭 넣어줘",
        )

        user_text = mocked_create.call_args.args[0]
        self.assertIn("협재해변을 꼭 넣어줘", user_text)
        mocked_save_result.assert_called_once()


class ItineraryStateSyncTests(unittest.TestCase):
    def test_deleted_db_stop_is_removed_from_engine_state(self) -> None:
        state = {
            "condition": {},
            "itinerary": {
                "days": [
                    {
                        "day": 1,
                        "title": "Day 1",
                        "stops": [
                            {"sequence": 1, "content_id": 11, "title": "A"},
                            {"sequence": 2, "content_id": 22, "title": "B"},
                        ],
                    }
                ]
            },
            "slots": [
                {
                    "day": 1,
                    "sequence": 1,
                    "candidates": [{"content_id": 11}],
                },
                {
                    "day": 1,
                    "sequence": 2,
                    "candidates": [{"content_id": 22}],
                },
            ],
            "used_content_ids": [11, 22],
        }
        schedule = [
            {
                "day": 1,
                "stops": [
                    {
                        "sequence": 2,
                        "title": "B",
                        "start_time": "11:00",
                        "notes": "kept",
                        "item_type": "spot",
                    }
                ],
            }
        ]

        merged = _merge_schedule_into_engine_state(state, schedule)

        stops = merged["itinerary"]["days"][0]["stops"]
        self.assertEqual([stop["content_id"] for stop in stops], [22])
        self.assertEqual(
            [(slot["day"], slot["sequence"]) for slot in merged["slots"]],
            [(1, 2)],
        )
        self.assertEqual(merged["used_content_ids"], [22])
        self.assertEqual(len(state["itinerary"]["days"][0]["stops"]), 2)


class PackageRecommendationAPIContractTests(unittest.TestCase):
    @patch.object(ItineraryViewSet, "get_object")
    def test_unauthenticated_request_is_rejected(self, mocked_get_object) -> None:
        request = APIRequestFactory().get(
            "/api/travel/itineraries/1/package-recommendations/"
        )
        view = ItineraryViewSet.as_view({"get": "package_recommendations"})

        response = view(request, pk=1)

        self.assertEqual(response.status_code, 401)
        mocked_get_object.assert_not_called()

    @patch("apps.travel.views.recommend_package_comparison")
    @patch.object(ItineraryViewSet, "get_object")
    def test_authenticated_request_uses_saved_engine_state(
        self,
        mocked_get_object,
        mocked_recommend,
    ) -> None:
        engine_state = {
            "condition": {"duration_days": 1, "party_type": "solo"},
            "itinerary": {"days": []},
        }
        mocked_get_object.return_value = SimpleNamespace(
            pk=1,
            engine_state=engine_state,
            start_date=date(2026, 1, 15),
            status=Itinerary.Status.CONFIRMED,
        )
        mocked_recommend.return_value = {
            "status": "completed",
            "recommendations": [{"package_id": "PKG-1"}],
        }
        request = APIRequestFactory().get(
            "/api/travel/itineraries/1/package-recommendations/",
            {"top_k": 3},
        )
        force_authenticate(request, user=SimpleNamespace(is_authenticated=True))
        view = ItineraryViewSet.as_view({"get": "package_recommendations"})

        response = view(request, pk=1)

        self.assertEqual(response.status_code, 200)
        expected_payload = {
            **engine_state,
            "condition": {
                **engine_state["condition"],
                "start_date": "2026-01-15",
            },
        }
        mocked_recommend.assert_called_once_with(expected_payload, itinerary_id=1)
        self.assertNotIn("start_date", engine_state["condition"])


@unittest.skipUnless(
    os.getenv("RUN_DB_CONTRACT_TESTS") == "1",
    "set RUN_DB_CONTRACT_TESTS=1 to inspect the real MySQL schema",
)
class PackageSchemaContractTests(unittest.TestCase):
    def _config(self) -> MySQLConfig:
        return MySQLConfig.from_env(PROJECT_ROOT / ".env")

    def _columns(self, table_name: str) -> set[str]:
        try:
            repository = MySQLPlaceRepository(self._config())
            with repository.connect() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
                        (table_name,),
                    )
                    return {str(row[0]) for row in cursor.fetchall()}
                finally:
                    cursor.close()
        except Exception as exc:
            self.skipTest(f"MySQL schema could not be inspected: {exc}")

    def test_travel_packages_schema_satisfies_current_application_contract(self) -> None:
        columns = self._columns("travel_packages")
        required_by_model_and_recommender = {
            "id",
            "package_id",
            "title",
            "summary",
            "region",
            "duration_days",
            "estimated_price",
            "companion",
            "tags",
            "is_active",
        }
        self.assertEqual(
            required_by_model_and_recommender - columns,
            set(),
            "travel_packages is missing columns still consumed by the application",
        )

    def test_package_profile_compatibility_columns_exist(self) -> None:
        package_columns = self._columns("travel_packages")
        self.assertIn("companion", package_columns)
        self.assertIn("tags", package_columns)

    def test_package_repository_reads_migrated_rows(self) -> None:
        try:
            packages = MySQLPackageRepository(self._config()).find_active_by_duration(1)
        except Exception as exc:
            self.fail(f"package repository cannot read the migrated schema: {exc}")
        self.assertTrue(packages)
        self.assertTrue(packages[0].match_profile["party_types"])
        self.assertTrue(packages[0].match_profile["themes"])


if __name__ == "__main__":
    unittest.main()
