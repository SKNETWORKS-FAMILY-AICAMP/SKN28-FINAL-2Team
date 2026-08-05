from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework.test import APIClient


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
