from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.travel.models import Itinerary
from apps.travel.views import ItineraryViewSet

from .services import recommend_package_comparison


class PackageRecommendationAPITests(SimpleTestCase):
    @patch("apps.travel.views.recommend_package_comparison")
    @patch.object(ItineraryViewSet, "get_object")
    def test_itinerary_action_uses_saved_rag_engine_state(
        self,
        mocked_get_object,
        mocked_recommend,
    ):
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
            "recommendations": [{"package_id": "VIRTUAL-JEJU-D1-01"}],
        }
        request = APIRequestFactory().get(
            "/api/travel/itineraries/1/package-recommendations/",
            {"top_k": 3},
        )
        force_authenticate(
            request,
            user=SimpleNamespace(is_authenticated=True),
        )
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

    @patch.object(ItineraryViewSet, "get_object")
    def test_draft_itinerary_cannot_request_recommendations(self, mocked_get_object):
        mocked_get_object.return_value = SimpleNamespace(
            status=Itinerary.Status.DRAFT,
        )
        request = APIRequestFactory().get(
            "/api/travel/itineraries/1/package-recommendations/"
        )
        force_authenticate(request, user=SimpleNamespace(is_authenticated=True))
        view = ItineraryViewSet.as_view({"get": "package_recommendations"})

        response = view(request, pk=1)

        self.assertEqual(response.status_code, 409)

    @patch.object(ItineraryViewSet, "get_serializer")
    @patch.object(ItineraryViewSet, "get_object")
    def test_confirm_action_changes_status(self, mocked_get_object, mocked_serializer):
        itinerary = SimpleNamespace(
            status=Itinerary.Status.DRAFT,
            engine_state={"itinerary": {"days": []}},
            save=Mock(),
        )
        mocked_get_object.return_value = itinerary
        mocked_serializer.return_value.data = {"id": 1, "status": "confirmed"}
        request = APIRequestFactory().post("/api/travel/itineraries/1/confirm/")
        force_authenticate(request, user=SimpleNamespace(is_authenticated=True))
        view = ItineraryViewSet.as_view({"post": "confirm"})

        response = view(request, pk=1)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(itinerary.status, Itinerary.Status.CONFIRMED)
        itinerary.save.assert_called_once_with(update_fields=["status", "updated_at"])


class PackageComparisonServiceTests(SimpleTestCase):
    @patch("apps.package_recommendation.services.recommend_packages")
    def test_builds_custom_quote_from_top_recommendation(self, mocked_recommend):
        stored_package = {
            "package_id": "VIRTUAL-JEJU-D3-01",
            "title": "제주 동부 2박3일",
            "estimated_price": 666_000,
        }
        mocked_recommend.return_value = {
            "status": "completed",
            "recommendations": [stored_package],
            "meta": {"candidate_count": 9},
        }

        result = recommend_package_comparison({}, itinerary_id=7)

        mocked_recommend.assert_called_once_with({}, top_k=1)
        self.assertEqual(result["stored_package"], stored_package)
        self.assertEqual(result["recommendations"], [stored_package])
        self.assertEqual(result["custom_package"]["itinerary_id"], 7)
        self.assertEqual(result["custom_package"]["price_per_person"], 746_000)
        self.assertTrue(result["custom_package"]["is_provisional_quote"])

    @patch("apps.package_recommendation.services.recommend_packages")
    def test_returns_empty_comparison_when_no_package_matches(self, mocked_recommend):
        mocked_recommend.return_value = {
            "status": "no_candidates",
            "recommendations": [],
            "meta": {"candidate_count": 0},
        }

        result = recommend_package_comparison({}, itinerary_id=7)

        self.assertIsNone(result["stored_package"])
        self.assertIsNone(result["custom_package"])