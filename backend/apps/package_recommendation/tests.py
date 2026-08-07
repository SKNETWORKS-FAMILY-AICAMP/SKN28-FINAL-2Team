from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from apps.travel.serializers import ItinerarySerializer
from apps.travel.views import ItineraryViewSet


class PackageRecommendationAPITests(SimpleTestCase):
    def test_direct_schedule_edit_updates_recommendation_engine_state(self):
        itinerary = SimpleNamespace(
            engine_state={
                "condition": {"duration_days": 1},
                "itinerary": {
                    "days": [
                        {
                            "day": 1,
                            "title": "기존 일정",
                            "stops": [
                                {
                                    "sequence": 1,
                                    "role": "visit",
                                    "title": "남길 관광지",
                                    "content_id": 101,
                                },
                                {
                                    "sequence": 2,
                                    "role": "visit",
                                    "title": "삭제할 관광지",
                                    "content_id": 102,
                                },
                            ],
                        }
                    ]
                },
                "used_content_ids": [101, 102],
            },
            save=Mock(),
        )

        ItinerarySerializer._sync_engine_state_days(
            itinerary,
            [
                {
                    "day_number": 1,
                    "items": [
                        {
                            "item_type": "spot",
                            "title": "남길 관광지",
                            "time": "10:00",
                        }
                    ],
                }
            ],
        )

        stops = itinerary.engine_state["itinerary"]["days"][0]["stops"]
        self.assertEqual([stop["content_id"] for stop in stops], [101])
        self.assertEqual(itinerary.engine_state["used_content_ids"], [101])
        itinerary.save.assert_called_once_with(update_fields=["engine_state"])

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
        mocked_get_object.return_value = SimpleNamespace(
            engine_state=engine_state,
            start_date=date(2026, 1, 15),
        )
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
        expected_payload = {
            **engine_state,
            "condition": {
                **engine_state["condition"],
                "start_date": "2026-01-15",
            },
        }
        mocked_recommend.assert_called_once_with(expected_payload, top_k=3)
        self.assertNotIn("start_date", engine_state["condition"])
