from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from apps.travel.views import ItineraryViewSet


class PackageRecommendationAPITests(SimpleTestCase):
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
