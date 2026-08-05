from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework.test import APIRequestFactory

from apps.travel.views import ItineraryViewSet


class PackageRecommendationAPITests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.payload = {
            "conditions": {"duration_days": 1, "party_type": "solo"},
            "itinerary": [
                {
                    "day": 1,
                    "sequence": 1,
                    "content_id": 101,
                    "title": "관광지 A",
                    "slot_kind": "tourism",
                }
            ],
        }

    @patch("apps.package_recommendation.views.recommend_packages")
    def test_recommendation_endpoint_returns_service_result(self, mocked_recommend):
        mocked_recommend.return_value = {
            "status": "completed",
            "recommendations": [{"package_id": "VIRTUAL-JEJU-D1-01"}],
        }

        response = self.client.post(
            reverse("package-recommendations"),
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["recommendations"][0]["package_id"], "VIRTUAL-JEJU-D1-01")
        mocked_recommend.assert_called_once()

    def test_recommendation_endpoint_rejects_missing_conditions(self):
        response = self.client.post(
            reverse("package-recommendations"),
            {"itinerary": self.payload["itinerary"]},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    @patch("apps.travel.views.recommend_packages")
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
        mocked_get_object.return_value = SimpleNamespace(engine_state=engine_state)
        mocked_recommend.return_value = {
            "status": "completed",
            "recommendations": [{"package_id": "VIRTUAL-JEJU-D1-01"}],
        }
        request = APIRequestFactory().get(
            "/api/travel/itineraries/1/package-recommendations/",
            {"top_k": 3},
        )
        view = ItineraryViewSet.as_view({"get": "package_recommendations"})

        response = view(request, pk=1)

        self.assertEqual(response.status_code, 200)
        mocked_recommend.assert_called_once_with(engine_state, top_k=3)
