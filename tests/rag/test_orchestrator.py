from __future__ import annotations

from copy import deepcopy
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


class NoReferenceRouteAdapter:
    def build_route_context(self, conditions):
        return {
            "user_constraints": conditions.to_dict(),
            "reference_trip_patterns": [],
            "context_policy": {},
        }


class FakeSlotRetriever:
    def retrieve(self, slot, conditions):
        is_meal = slot.slot_kind == "meal"
        content_id = (
            900000 + slot.day * 1000 + slot.sequence
            if is_meal
            else slot.day * 100 + slot.sequence
        )
        candidate = RetrievedPlace(
            content_id=content_id,
            title=f"Day {slot.day} 장소 {slot.sequence}",
            latitude=33.45,
            longitude=126.50,
            similarity_score=0.9,
            rank=1,
            target_collection="restaurants" if is_meal else "attractions",
            itinerary_role="meal" if is_meal else "visit",
            opening_hours="07:00-22:00" if is_meal else "09:00-18:00",
            rating=4.6 if is_meal else None,
            slot_score=0.95,
        )
        alternative = RetrievedPlace(
            content_id=content_id + 500000,
            title=f"Day {slot.day} 대체 장소 {slot.sequence}",
            latitude=33.451,
            longitude=126.501,
            similarity_score=0.85,
            rank=2,
            target_collection="restaurants" if is_meal else "attractions",
            itinerary_role="meal" if is_meal else "visit",
            opening_hours="07:00-22:00" if is_meal else "09:00-18:00",
            rating=4.2 if is_meal else None,
            slot_score=0.85,
        )
        return SlotCandidates(
            slot,
            "자연 관광지",
            (candidate, alternative),
        )


class MissingLunchSlotRetriever(FakeSlotRetriever):
    def retrieve(self, slot, conditions):
        if slot.slot_kind == "meal" and slot.meal_type == "lunch":
            return SlotCandidates(slot, "점심 식당", ())
        return super().retrieve(slot, conditions)


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


class FourDayConditionLLM(FakeLLM):
    def extract_conditions(self, **kwargs):
        return TravelConditions.from_mapping(
            {
                "duration_days": 4,
                "party_type": "non_family_two",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature", "culture"],
                "exit_point": "제주국제공항",
            }
        )


class ThreeDayRouteAdapter:
    def build_route_context(self, conditions):
        context = deepcopy(ROUTE_CONTEXT)
        base_day = context["reference_trip_patterns"][0]["days"][0]
        context["reference_trip_patterns"][0]["days"] = [
            {
                **deepcopy(base_day),
                "day": day,
                "region": {
                    "center": {
                        "latitude": 33.40 + day / 100,
                        "longitude": 126.50 + day / 100,
                    },
                    "vector_search_radius_km": 8.0,
                },
            }
            for day in range(1, 4)
        ]
        return context


class OrchestratorTests(unittest.TestCase):
    def test_asks_user_when_meal_candidates_are_unavailable(self) -> None:
        llm = FakeLLM()
        orchestrator = RagOrchestrator(
            condition_service=ConditionExtractionService(llm),
            route_adapter=FakeRouteAdapter(),
            slot_retriever=MissingLunchSlotRetriever(),
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

        self.assertEqual(result["status"], "clarification_required")
        self.assertEqual(
            result["clarification_kind"],
            "meal_candidate_unavailable",
        )
        self.assertEqual(result["missing_slots"], ["Day 1 #102"])
        self.assertIn("점심", result["clarification_questions"][0])
        self.assertEqual(
            result["clarification_options"][0]["selected_options"],
            {"meal_search_radius_km": 12},
        )
        skip_option = next(
            option
            for option in result["clarification_options"]
            if option["value"] == "skip_unavailable_meals"
        )
        self.assertEqual(
            skip_option["selected_options"],
            {
                "skipped_meals": [
                    {"day": 1, "meal_type": "lunch"},
                ]
            },
        )
        self.assertEqual(result["itinerary"], [])

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
                "start_point": "제주국제공항",
                "end_point": "제주항",
                "accommodation": "제주시 숙소",
            }
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(result["itinerary"]), 5)
        self.assertEqual(llm.extract_calls, 0)
        self.assertEqual(result["meta"]["input_mode"], "frontend_selections")
        self.assertEqual(result["meta"]["places_per_day"], 3)
        self.assertEqual(result["meta"]["route_strategy"], "aihub_pattern")
        self.assertIsNone(result["meta"]["aihub_fallback_reason"])
        self.assertEqual(result["conditions"]["entry_point"], "제주국제공항")
        self.assertEqual(result["conditions"]["exit_point"], "제주항")
        self.assertEqual(
            result["conditions"]["accommodation_address"],
            "제주시 숙소",
        )

    def test_uses_tourapi_only_when_aihub_has_no_reference_route(self) -> None:
        llm = FakeLLM()
        orchestrator = RagOrchestrator(
            condition_service=ConditionExtractionService(llm),
            route_adapter=NoReferenceRouteAdapter(),
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
        self.assertFalse(result["meta"]["aihub_used"])
        self.assertTrue(result["meta"]["tourapi_rag_used"])
        self.assertEqual(
            result["meta"]["route_strategy"],
            "tourapi_only_fallback",
        )
        self.assertEqual(
            result["meta"]["aihub_fallback_reason"],
            "no_reference_pattern",
        )
        tourism_slots = [
            item["slot"]
            for item in result["slot_candidates"]
            if item["slot"]["slot_kind"] == "tourism"
        ]
        self.assertEqual(len(tourism_slots), 3)
        self.assertTrue(
            all(
                slot["template_source"] == "tourapi_only_fallback"
                for slot in tourism_slots
            )
        )

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
        self.assertEqual(len(result["itinerary"]), 5)
        self.assertTrue(result["meta"]["llm_repaired"])
        self.assertEqual(llm.repair_calls, 1)
        self.assertEqual(result["meta"]["aihub_tourapi_mapping"], "ignored")

    def test_replaces_only_the_requested_stop(self) -> None:
        llm = FakeLLM()
        orchestrator = RagOrchestrator(
            condition_service=ConditionExtractionService(llm),
            route_adapter=FakeRouteAdapter(),
            slot_retriever=FakeSlotRetriever(),
            llm=llm,
        )
        original = orchestrator.run(
            selected_options={
                "duration_days": 1,
                "party_type": "solo",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature"],
            }
        )
        original_ids = {
            stop["sequence"]: stop["content_id"]
            for stop in original["itinerary"]
        }

        revised = orchestrator.revise(
            previous_result=original,
            message="1일차의 Day 1 장소 2를 다른 걸로 교체해 주세요.",
        )
        revised_ids = {
            stop["sequence"]: stop["content_id"]
            for stop in revised["itinerary"]
        }

        self.assertEqual(revised["status"], "completed")
        self.assertEqual(revised_ids[1], original_ids[1])
        self.assertNotEqual(revised_ids[2], original_ids[2])
        self.assertEqual(revised_ids[3], original_ids[3])
        self.assertEqual(revised_ids[102], original_ids[102])
        self.assertEqual(revised_ids[103], original_ids[103])
        self.assertEqual(
            revised["meta"]["edit_mode"],
            "targeted_replacement",
        )
        self.assertEqual(revised["meta"]["edited_day"], 1)
        self.assertEqual(revised["meta"]["edited_sequence"], 2)
        self.assertEqual(revised["meta"]["unchanged_place_count"], 4)

    def test_preserves_itinerary_when_replacement_target_is_unknown(self) -> None:
        llm = FakeLLM()
        orchestrator = RagOrchestrator(
            condition_service=ConditionExtractionService(llm),
            route_adapter=FakeRouteAdapter(),
            slot_retriever=FakeSlotRetriever(),
            llm=llm,
        )
        original = orchestrator.run(
            selected_options={
                "duration_days": 1,
                "party_type": "solo",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature"],
            }
        )

        revised = orchestrator.revise(
            previous_result=original,
            message="1일차의 존재하지 않는 장소를 다른 걸로 교체해 주세요.",
        )

        self.assertEqual(revised["status"], "clarification_required")
        self.assertEqual(revised["itinerary"], original["itinerary"])
        self.assertTrue(revised["meta"]["itinerary_preserved"])

    def test_fills_aihub_pattern_shorter_than_requested_trip(self) -> None:
        llm = TwoDayConditionLLM()
        orchestrator = RagOrchestrator(
            condition_service=ConditionExtractionService(llm),
            route_adapter=FakeRouteAdapter(),
            slot_retriever=FakeSlotRetriever(),
            llm=llm,
        )

        result = orchestrator.run(message="혼자 렌터카로 2일 자연 여행")

        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(result["itinerary"]), 10)
        self.assertEqual(result["meta"]["synthesized_route_days"], [2])
        self.assertEqual(result["meta"]["synthesized_slot_count"], 3)
        self.assertTrue(result["meta"]["tourapi_rag_used"])

    def test_fills_missing_day_four_and_generates_twelve_places(self) -> None:
        llm = FourDayConditionLLM()
        orchestrator = RagOrchestrator(
            condition_service=ConditionExtractionService(llm),
            route_adapter=ThreeDayRouteAdapter(),
            slot_retriever=FakeSlotRetriever(),
            llm=llm,
        )

        result = orchestrator.run(
            message=(
                "제주에서 연인과 렌터카로 3박 4일 자연과 문화 여행, "
                "제주공항에서 종료"
            )
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(result["itinerary"]), 20)
        self.assertEqual(
            result["meta"]["aihub_original_slot_counts"],
            {1: 3, 2: 3, 3: 3, 4: 0},
        )
        self.assertEqual(result["meta"]["synthesized_route_days"], [4])
        self.assertEqual(result["meta"]["synthesized_slot_count"], 3)
        day_four_slots = [
            item
            for item in result["slot_candidates"]
            if item["slot"]["day"] == 4
            and item["slot"]["slot_kind"] == "tourism"
        ]
        self.assertEqual(len(day_four_slots), 3)
        self.assertTrue(
            all(
                item["slot"]["template_source"] == "synthetic_gap_fill"
                for item in day_four_slots
            )
        )
        self.assertEqual(
            day_four_slots[-1]["slot"]["route_anchor"],
            "제주국제공항",
        )


if __name__ == "__main__":
    unittest.main()
