from __future__ import annotations

import unittest

from src.rag.conditions import ConditionExtractionService
from src.rag.models import (
    ItineraryChoice,
    ItineraryDraft,
    RetrievedPlace,
    SlotCandidates,
    TravelConditions,
)
from src.rag.orchestrator import RagOrchestrator
from src.rag.retrieval import route_slots


ROUTE_CONTEXT = {
    "user_constraints": {},
    "reference_trip_patterns": [
        {
            "reference_trip_id": "aihub-trip:test",
            "match_score": 91.0,
            "match_confidence": "high",
            "matched_on": ["party", "transport"],
            "conflicts": [],
            "profile": {"duration_days": 1},
            "days": [
                {
                    "day": 1,
                    "region": {
                        "center": {
                            "latitude": 33.45,
                            "longitude": 126.50,
                        },
                        "vector_search_radius_km": 8.0,
                    },
                    "slots": [
                        {
                            "sequence": 1,
                            "role": "visit",
                            "category": "nature",
                            "target_collections": ["attractions"],
                            "itinerary_roles": ["visit"],
                            "stay_minutes": 60,
                            "location_hint": None,
                        },
                        {
                            "sequence": 2,
                            "role": "visit",
                            "category": "nature",
                            "target_collections": ["attractions"],
                            "itinerary_roles": ["visit"],
                            "stay_minutes": 60,
                            "location_hint": None,
                        },
                        {
                            "sequence": 3,
                            "role": "visit",
                            "category": "nature",
                            "target_collections": ["attractions"],
                            "itinerary_roles": ["visit"],
                            "stay_minutes": 60,
                            "location_hint": None,
                        },
                    ],
                }
            ],
        }
    ],
    "context_policy": {
        "place_source": "tourapi_vector_candidates_only",
        "aihub_tourapi_mapping": "ignored",
    },
}


class FakeLLM:
    def __init__(self) -> None:
        self.repair_calls = 0
        self.extract_calls = 0

    def extract_conditions(self, **kwargs):
        self.extract_calls += 1
        return TravelConditions.from_mapping(
            {
                "duration_days": 1,
                "party_type": "solo",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature"],
            }
        )

    def generate_itinerary(self, context):
        return ItineraryDraft(
            (
                ItineraryChoice(
                    1,
                    1,
                    999,
                    60,
                    "화이트리스트 밖의 초안",
                ),
                ItineraryChoice(1, 2, 102, 60, "두 번째 슬롯"),
                ItineraryChoice(1, 3, 103, 60, "세 번째 슬롯"),
            )
        )

    def repair_itinerary(self, **kwargs):
        self.repair_calls += 1
        return ItineraryDraft(
            (
                ItineraryChoice(
                    1,
                    1,
                    101,
                    60,
                    "검증 오류를 수정한 TourAPI 후보입니다.",
                ),
                ItineraryChoice(1, 2, 102, 60, "두 번째 슬롯"),
                ItineraryChoice(1, 3, 103, 60, "세 번째 슬롯"),
            )
        )


class FakeRouteAdapter:
    def build_route_context(self, conditions):
        return ROUTE_CONTEXT


class FakeSlotRetriever:
    def retrieve(self, slot, conditions):
        candidate = RetrievedPlace(
            content_id=100 + slot.sequence,
            title="테스트 자연 관광지",
            latitude=33.45,
            longitude=126.50,
            similarity_score=0.9,
            rank=1,
            target_collection="attractions",
            itinerary_role="visit",
            opening_hours="09:00-18:00",
            slot_score=0.95,
        )
        return SlotCandidates(slot, "자연 관광지", (candidate,))


class TwoDayConditionLLM(FakeLLM):
    def extract_conditions(self, **kwargs):
        return TravelConditions.from_mapping(
            {
                "duration_days": 2,
                "party_type": "solo",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature"],
            }
        )


class OrchestratorTests(unittest.TestCase):
    def test_builds_schedule_directly_from_frontend_selections(self) -> None:
        llm = FakeLLM()
        orchestrator = RagOrchestrator(
            condition_service=ConditionExtractionService(llm),
            route_adapter=FakeRouteAdapter(),
            slot_retriever=FakeSlotRetriever(),
            llm=llm,
        )

        result = orchestrator.run(
            selected_options={
                "duration_days": 1,
                "party_type": "solo",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature"],
            }
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(result["itinerary"]), 3)
        self.assertEqual(llm.extract_calls, 0)
        self.assertEqual(result["meta"]["input_mode"], "frontend_selections")
        self.assertEqual(result["meta"]["places_per_day"], 3)

    def test_repairs_invalid_llm_id_and_completes(self) -> None:
        llm = FakeLLM()
        orchestrator = RagOrchestrator(
            condition_service=ConditionExtractionService(llm),
            route_adapter=FakeRouteAdapter(),
            slot_retriever=FakeSlotRetriever(),
            llm=llm,
        )

        result = orchestrator.run(message="혼자 렌터카로 자연 여행")

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["itinerary"][0]["content_id"], 101)
        self.assertEqual(len(result["itinerary"]), 3)
        self.assertTrue(result["meta"]["llm_repaired"])
        self.assertEqual(llm.repair_calls, 1)
        self.assertEqual(result["meta"]["aihub_tourapi_mapping"], "ignored")

    def test_rejects_aihub_pattern_shorter_than_requested_trip(self) -> None:
        llm = TwoDayConditionLLM()
        orchestrator = RagOrchestrator(
            condition_service=ConditionExtractionService(llm),
            route_adapter=FakeRouteAdapter(),
            slot_retriever=FakeSlotRetriever(),
            llm=llm,
        )

        result = orchestrator.run(message="혼자 렌터카로 2일 자연 여행")

        self.assertEqual(result["status"], "route_template_incomplete")
        self.assertEqual(result["missing_days"], [2])
        self.assertFalse(result["meta"]["tourapi_rag_used"])


if __name__ == "__main__":
    unittest.main()
