from __future__ import annotations

import os
from datetime import date
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from rest_framework.test import APIRequestFactory, force_authenticate

from apps.travel.models import Itinerary, ItineraryDay
from apps.travel.serializers import ItinerarySerializer
from apps.travel.services import (
    _clone_itinerary_as_draft,
    _merge_schedule_into_engine_state,
    generate_itinerary,
    prepare_itinerary_for_edit,
)
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


class ItineraryEditPreparationTests(unittest.TestCase):
    @patch("apps.travel.views.prepare_itinerary_for_edit")
    @patch.object(ItineraryViewSet, "get_serializer")
    @patch.object(ItineraryViewSet, "get_object")
    def test_prepare_edit_action_returns_editable_itinerary(
        self,
        mocked_get_object,
        mocked_get_serializer,
        mocked_prepare,
    ) -> None:
        source = SimpleNamespace(id=1)
        editable = SimpleNamespace(id=2)
        mocked_get_object.return_value = source
        mocked_prepare.return_value = (editable, True)
        mocked_get_serializer.return_value.data = {
            "id": 2,
            "status": Itinerary.Status.DRAFT,
        }
        request = APIRequestFactory().post(
            "/api/travel/itineraries/1/prepare-edit/"
        )
        force_authenticate(
            request,
            user=SimpleNamespace(is_authenticated=True),
        )
        view = ItineraryViewSet.as_view({"post": "prepare_edit"})

        response = view(request, pk=1)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {"id": 2, "status": Itinerary.Status.DRAFT, "copied": True},
        )
        mocked_prepare.assert_called_once_with(source)

    def test_unbooked_confirmed_itinerary_reopens_and_invalidates_quote(self) -> None:
        cart_items = Mock()
        itinerary = SimpleNamespace(
            status=Itinerary.Status.CONFIRMED,
            reservations=SimpleNamespace(
                exists=Mock(return_value=False),
            ),
            cart_product_items=SimpleNamespace(
                all=Mock(return_value=cart_items),
            ),
            selected_package=42,
            is_public=True,
            share_token="shared-token",
            save=Mock(),
        )

        editable, copied = prepare_itinerary_for_edit.__wrapped__(itinerary)

        self.assertIs(editable, itinerary)
        self.assertFalse(copied)
        self.assertEqual(itinerary.status, Itinerary.Status.DRAFT)
        self.assertIsNone(itinerary.selected_package)
        self.assertFalse(itinerary.is_public)
        self.assertIsNone(itinerary.share_token)
        cart_items.delete.assert_called_once_with()
        itinerary.save.assert_called_once_with(
            update_fields=[
                "status",
                "selected_package",
                "is_public",
                "share_token",
                "updated_at",
            ]
        )

    @patch("apps.travel.services._clone_itinerary_as_draft")
    def test_booked_itinerary_returns_a_draft_copy(self, mocked_clone) -> None:
        clone = SimpleNamespace(status=Itinerary.Status.DRAFT)
        mocked_clone.return_value = clone
        itinerary = SimpleNamespace(
            status=Itinerary.Status.CONFIRMED,
            reservations=SimpleNamespace(
                exists=Mock(return_value=True),
            ),
        )

        editable, copied = prepare_itinerary_for_edit.__wrapped__(itinerary)

        self.assertIs(editable, clone)
        self.assertTrue(copied)
        mocked_clone.assert_called_once_with(itinerary)

    @patch("apps.travel.services.ItineraryItem.objects.bulk_create")
    @patch("apps.travel.services.ItineraryDay.objects.create")
    @patch("apps.travel.services.Itinerary.objects.create")
    def test_draft_copy_preserves_schedule_but_resets_links(
        self,
        mocked_create_itinerary,
        mocked_create_day,
        mocked_bulk_create,
    ) -> None:
        clone = Itinerary(
            id=2,
            start_date=date(2026, 1, 15),
            end_date=date(2026, 1, 16),
        )
        cloned_day = ItineraryDay(
            id=20,
            itinerary=clone,
            day_number=1,
            date=date(2026, 1, 15),
        )
        mocked_create_itinerary.return_value = clone
        mocked_create_day.return_value = cloned_day
        item = SimpleNamespace(
            order=1,
            time="09:00",
            item_type="spot",
            title="협재해변",
            description="바다",
            thumbnail="image.jpg",
            spot=None,
            restaurant=None,
            accommodation=None,
            latitude=33.3,
            longitude=126.2,
            memo="",
        )
        day = SimpleNamespace(
            day_number=1,
            date=date(2026, 1, 15),
            items=SimpleNamespace(all=Mock(return_value=[item])),
        )
        source = SimpleNamespace(
            user=SimpleNamespace(id=1),
            title="제주 여행",
            subtitle="바다 여행",
            start_date=date(2026, 1, 15),
            end_date=date(2026, 1, 16),
            companion_type="friend",
            age_group="30",
            companion_count=2,
            style="힐링",
            engine_state={"itinerary": {"days": [{"day": 1}]}},
            days=SimpleNamespace(
                prefetch_related=Mock(
                    return_value=SimpleNamespace(
                        all=Mock(return_value=[day])
                    )
                )
            ),
        )

        result = _clone_itinerary_as_draft(source)

        self.assertIs(result, clone)
        create_kwargs = mocked_create_itinerary.call_args.kwargs
        self.assertEqual(create_kwargs["status"], Itinerary.Status.DRAFT)
        self.assertIsNone(create_kwargs["selected_package"])
        self.assertIsNone(create_kwargs["share_token"])
        self.assertIsNot(create_kwargs["engine_state"], source.engine_state)
        mocked_create_day.assert_called_once_with(
            itinerary=clone,
            day_number=1,
            date=date(2026, 1, 15),
        )
        cloned_items = mocked_bulk_create.call_args.args[0]
        self.assertEqual(len(cloned_items), 1)
        self.assertEqual(cloned_items[0].title, "협재해변")
        self.assertIs(cloned_items[0].day, cloned_day)


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
