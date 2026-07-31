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
from src.rag.routing import RouteEstimate


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


class CountingSlotRetriever(FakeSlotRetriever):
    def __init__(self) -> None:
        self.calls = 0

    def retrieve(self, slot, conditions):
        self.calls += 1
        return super().retrieve(slot, conditions)


class AnchorEchoSlotRetriever:
    def __init__(self) -> None:
        self.slots = []

    def retrieve(self, slot, conditions):
        self.slots.append(slot)
        candidate = RetrievedPlace(
            content_id=700000 + len(self.slots),
            title=f"앵커 인접 장소 {len(self.slots)}",
            latitude=float(slot.latitude),
            longitude=float(slot.longitude),
            similarity_score=0.8,
            rank=1,
            target_collection="attractions",
            itinerary_role="visit",
            opening_hours="09:00-20:00",
            slot_score=0.8,
        )
        return SlotCandidates(slot, "앵커 인접 관광지", (candidate,))


class AlwaysFarRouteProvider:
    def estimate(self, origin, destination, *, transport):
        return RouteEstimate(
            distance_km=100.0,
            duration_minutes=180,
            provider="always_far_test",
            verified=True,
        )


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
            [
                option["value"]
                for option in result["clarification_options"]
            ],
            [
                "skip_unavailable_meals",
                "enter_meal_region",
                "change_meal_menu",
            ],
        )
        self.assertTrue(result["meta"]["tourism_itinerary_preserved"])
        self.assertTrue(result["meta"]["partial_result"])
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
        self.assertEqual(len(result["itinerary"]), 3)
        self.assertTrue(result["meta"]["provisional_tourism_schedule"])
        self.assertTrue(result["validation"]["valid"])

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

    def test_builds_schedule_from_minimum_frontend_values(self) -> None:
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
                "companion_count": 2,
            }
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(result["itinerary"]), 5)
        self.assertEqual(result["conditions"]["party_type"], "non_family_two")
        self.assertEqual(result["conditions"]["local_transport"], "mixed")
        self.assertEqual(
            result["conditions"]["preferred_visit_types"],
            ["nature", "culture", "experience"],
        )
        self.assertEqual(result["meta"]["places_per_day"], 3)

    def test_creates_initial_itinerary_from_guided_four_inputs(self) -> None:
        llm = FakeLLM()
        orchestrator = RagOrchestrator(
            condition_service=ConditionExtractionService(llm),
            route_adapter=FakeRouteAdapter(),
            slot_retriever=FakeSlotRetriever(),
            llm=llm,
        )

        result = orchestrator.create_initial_itinerary(
            duration_days=1,
            party_size=2,
            local_transport="rental_car",
            travel_style="healing",
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(result["itinerary"]), 5)
        self.assertEqual(result["conditions"]["travel_styles"], ["healing"])
        self.assertEqual(
            result["conditions"]["preferred_visit_types"],
            ["nature", "trail"],
        )
        self.assertEqual(
            result["meta"]["interaction_flow"],
            "guided_initial_itinerary_v1",
        )
        self.assertEqual(
            result["meta"]["guided_input_fields"],
            [
                "duration_days",
                "party_size",
                "local_transport",
                "travel_style",
            ],
        )

    def test_continues_completed_itinerary_with_natural_language(self) -> None:
        llm = FakeLLM()
        orchestrator = RagOrchestrator(
            condition_service=ConditionExtractionService(llm),
            route_adapter=FakeRouteAdapter(),
            slot_retriever=FakeSlotRetriever(),
            llm=llm,
        )
        original = orchestrator.create_initial_itinerary(
            duration_days=1,
            party_size=2,
            local_transport="rental_car",
            travel_style="popular",
        )

        revised = orchestrator.continue_itinerary(
            previous_result=original,
            message="자연 관광지를 더 선호합니다.",
        )

        self.assertEqual(revised["status"], "completed")
        self.assertEqual(
            revised["meta"]["interaction_flow"],
            "natural_language_revision_v1",
        )
        self.assertEqual(
            revised["meta"]["edit_mode"],
            "condition_update_regeneration",
        )

    def test_adds_tourism_slot_only_after_explicit_request(self) -> None:
        llm = FakeLLM()
        orchestrator = RagOrchestrator(
            condition_service=ConditionExtractionService(llm),
            route_adapter=FakeRouteAdapter(),
            slot_retriever=FakeSlotRetriever(),
            llm=llm,
        )
        original = orchestrator.create_initial_itinerary(
            duration_days=2,
            party_size=2,
            local_transport="rental_car",
            travel_style="activity",
        )

        original_counts = {
            day: len(
                [
                    stop
                    for stop in original["itinerary"]
                    if stop["slot_kind"] == "tourism"
                    and stop["day"] == day
                ]
            )
            for day in (1, 2)
        }
        self.assertEqual(original_counts, {1: 3, 2: 3})

        revised = orchestrator.continue_itinerary(
            previous_result=original,
            message="2일차에 관광지 1곳 추가해 주세요.",
        )

        revised_counts = {
            day: len(
                [
                    stop
                    for stop in revised["itinerary"]
                    if stop["slot_kind"] == "tourism"
                    and stop["day"] == day
                ]
            )
            for day in (1, 2)
        }
        self.assertEqual(revised["status"], "completed")
        self.assertEqual(revised_counts, {1: 3, 2: 4})
        self.assertEqual(
            revised["meta"]["edit_mode"],
            "tourism_slot_addition",
        )
        self.assertEqual(
            revised["meta"]["tourism_places_by_day"],
            {1: 3, 2: 4},
        )

    def test_slot_addition_without_day_requests_clarification(self) -> None:
        llm = FakeLLM()
        orchestrator = RagOrchestrator(
            condition_service=ConditionExtractionService(llm),
            route_adapter=FakeRouteAdapter(),
            slot_retriever=FakeSlotRetriever(),
            llm=llm,
        )
        original = orchestrator.create_initial_itinerary(
            duration_days=1,
            party_size=2,
            local_transport="rental_car",
            travel_style="healing",
        )

        revised = orchestrator.continue_itinerary(
            previous_result=original,
            message="관광지 한 곳 추가해 주세요.",
        )

        self.assertEqual(revised["status"], "clarification_required")
        self.assertIn("추가할 일차", revised["message"])

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

    def test_repairs_invalid_llm_id_locally_before_paid_retry(self) -> None:
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
        self.assertFalse(result["meta"]["llm_repaired"])
        self.assertTrue(result["meta"]["deterministic_fallback_used"])
        self.assertEqual(llm.repair_calls, 0)
        self.assertEqual(result["meta"]["aihub_tourapi_mapping"], "ignored")

    def test_retrieves_candidates_again_instead_of_llm_repair(self) -> None:
        llm = FakeLLM()
        retriever = CountingSlotRetriever()
        orchestrator = RagOrchestrator(
            condition_service=ConditionExtractionService(llm),
            route_adapter=FakeRouteAdapter(),
            slot_retriever=retriever,
            llm=llm,
            route_provider=AlwaysFarRouteProvider(),
        )

        result = orchestrator.run(message="혼자 렌터카로 자연 여행")

        self.assertEqual(result["status"], "validation_failed")
        self.assertEqual(llm.repair_calls, 0)
        self.assertFalse(result["meta"]["llm_repaired"])
        self.assertTrue(result["meta"]["candidate_retrieval_retry_used"])
        self.assertEqual(result["meta"]["candidate_retrieval_retry_count"], 1)
        self.assertGreater(retriever.calls, 5)

    def test_validation_retry_reanchors_each_slot_to_previous_place(self) -> None:
        llm = FakeLLM()
        retriever = AnchorEchoSlotRetriever()
        orchestrator = RagOrchestrator(
            condition_service=ConditionExtractionService(llm),
            route_adapter=FakeRouteAdapter(),
            slot_retriever=retriever,
            llm=llm,
        )
        conditions = TravelConditions.from_mapping(
            {
                "duration_days": 1,
                "party_type": "solo",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature"],
                "entry_point": "제주국제공항",
                "avoid_long_distance": True,
            }
        )
        original_slots = route_slots(ROUTE_CONTEXT, duration_days=1)
        original = [
            SlotCandidates(
                slot,
                "기존 AIHub 슬롯",
                (
                    RetrievedPlace(
                        content_id=800000 + slot.sequence,
                        title=f"기존 장소 {slot.sequence}",
                        latitude=slot.latitude,
                        longitude=slot.longitude,
                        similarity_score=0.9,
                        rank=1,
                        target_collection="attractions",
                        itinerary_role="visit",
                        opening_hours="09:00-20:00",
                        slot_score=0.9,
                    ),
                ),
            )
            for slot in original_slots
        ]

        retried = orchestrator._retrieve_validation_retry_candidates(
            conditions=conditions,
            tourism_retrieved=original,
            meal_slots=(),
            broad_fallback_slots={},
            places_per_day_by_day={1: 3},
            avoided_ids=set(),
        )

        self.assertEqual(len(retried), 3)
        self.assertAlmostEqual(retriever.slots[0].latitude, 33.5104, places=4)
        self.assertAlmostEqual(retriever.slots[0].longitude, 126.4913, places=4)
        self.assertEqual(
            retriever.slots[1].latitude,
            retried[0].candidates[0].latitude,
        )
        self.assertEqual(
            retriever.slots[1].longitude,
            retried[0].candidates[0].longitude,
        )

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
