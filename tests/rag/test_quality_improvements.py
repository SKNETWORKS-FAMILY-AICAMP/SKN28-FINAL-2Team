from __future__ import annotations

import unittest

from src.rag.conditions import ConditionExtractionService
from src.rag.models import (
    ItineraryChoice,
    ItineraryDraft,
    RetrievedPlace,
    SlotCandidates,
    SlotRequest,
    TravelConditions,
)
from src.rag.orchestrator import RagOrchestrator
from src.rag.routing import RouteEstimate
from src.rag.validation import ValidationPolicy, validate_and_schedule

from .test_orchestrator import FakeLLM, FakeRouteAdapter, FakeSlotRetriever


class RecordingRoadProvider:
    def __init__(self) -> None:
        self.calls = []

    def estimate(self, origin, destination, *, transport):
        self.calls.append((origin, destination, transport))
        return RouteEstimate(
            distance_km=4.2,
            duration_minutes=12,
            provider="test_road_network",
            verified=True,
        )


def one_slot(
    *,
    day: int = 1,
    latitude: float = 33.45,
    longitude: float = 126.50,
    opening_hours: str = "09:00-18:00",
    closed_days: str = "연중무휴",
) -> SlotCandidates:
    slot = SlotRequest(
        day=day,
        sequence=1,
        role="visit",
        category="nature",
        target_collections=("attractions",),
        itinerary_roles=("visit",),
        stay_minutes=60,
        latitude=latitude,
        longitude=longitude,
        radius_km=8.0,
    )
    place = RetrievedPlace(
        content_id=100 + day,
        title=f"Day {day} 검증 장소",
        latitude=latitude,
        longitude=longitude,
        similarity_score=0.9,
        rank=1,
        target_collection="attractions",
        itinerary_role="visit",
        opening_hours=opening_hours,
        closed_days=closed_days,
        slot_score=0.9,
    )
    return SlotCandidates(slot=slot, query="자연", candidates=(place,))


def draft_for(*slots: SlotCandidates) -> ItineraryDraft:
    return ItineraryDraft(
        tuple(
            ItineraryChoice(
                day=item.slot.day,
                slot_sequence=item.slot.sequence,
                content_id=item.candidates[0].content_id,
                stay_minutes=60,
                reason="검증 가능한 후보를 선택했습니다.",
            )
            for item in slots
        )
    )


class QualityImprovementTests(unittest.TestCase):
    def test_verified_road_provider_produces_booking_ready_result(self) -> None:
        slot = one_slot()
        provider = RecordingRoadProvider()
        conditions = TravelConditions.from_mapping(
            {
                "duration_days": 1,
                "party_type": "solo",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature"],
                "entry_point": "출발지",
                "entry_latitude": 33.50,
                "entry_longitude": 126.49,
                "exit_point": "도착지",
                "exit_latitude": 33.51,
                "exit_longitude": 126.48,
            }
        )

        result = validate_and_schedule(
            draft_for(slot),
            (slot,),
            conditions,
            route_provider=provider,
        )

        self.assertTrue(result.valid)
        self.assertFalse(result.warnings)
        self.assertTrue(result.to_dict()["ready_for_booking"])
        self.assertEqual(len(provider.calls), 2)
        self.assertEqual(
            result.schedule[0].route_source,
            "test_road_network",
        )
        self.assertTrue(result.schedule[0].route_verified)

    def test_unknown_facts_are_exposed_as_warnings(self) -> None:
        slot = one_slot(
            latitude=0.0,
            longitude=0.0,
            opening_hours="",
            closed_days="",
        )
        conditions = TravelConditions.from_mapping(
            {
                "duration_days": 1,
                "party_type": "solo",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature"],
            }
        )

        result = validate_and_schedule(
            draft_for(slot),
            (slot,),
            conditions,
        )

        self.assertTrue(result.valid)
        self.assertFalse(result.to_dict()["ready_for_booking"])
        codes = {warning.code for warning in result.warnings}
        self.assertIn("missing_route_coordinates", codes)
        self.assertIn("opening_hours_unverified", codes)

    def test_strict_policy_blocks_unknown_facts(self) -> None:
        slot = one_slot(
            latitude=0.0,
            longitude=0.0,
            opening_hours="",
            closed_days="",
        )
        conditions = TravelConditions.from_mapping(
            {
                "duration_days": 1,
                "party_type": "solo",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature"],
            }
        )

        result = validate_and_schedule(
            draft_for(slot),
            (slot,),
            conditions,
            policy=ValidationPolicy(
                block_missing_coordinates=True,
                block_missing_opening_hours=True,
            ),
        )

        self.assertFalse(result.valid)
        codes = {issue.code for issue in result.issues}
        self.assertIn("missing_route_coordinates", codes)
        self.assertIn("opening_hours_unverified", codes)

    def test_weekly_closure_blocks_the_actual_travel_date(self) -> None:
        slot = one_slot(closed_days="매주 월요일 휴무")
        conditions = TravelConditions.from_mapping(
            {
                "start_date": "2026-07-27",
                "duration_days": 1,
                "party_type": "solo",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature"],
            }
        )

        result = validate_and_schedule(
            draft_for(slot),
            (slot,),
            conditions,
        )

        self.assertFalse(result.valid)
        self.assertIn(
            "closed_on_travel_date",
            {issue.code for issue in result.issues},
        )

    def test_accommodation_is_used_for_daily_departure_and_return(self) -> None:
        slot = one_slot(day=2)
        provider = RecordingRoadProvider()
        conditions = TravelConditions.from_mapping(
            {
                "duration_days": 2,
                "party_type": "solo",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature"],
                "accommodation": "제주 숙소",
                "accommodation_latitude": 33.48,
                "accommodation_longitude": 126.52,
            }
        )

        result = validate_and_schedule(
            draft_for(slot),
            (slot,),
            conditions,
            route_provider=provider,
        )

        self.assertTrue(result.valid)
        self.assertEqual(len(provider.calls), 2)
        self.assertEqual(provider.calls[0][0], (33.48, 126.52))
        self.assertEqual(provider.calls[1][1], (33.48, 126.52))

    def test_balanced_pace_keeps_three_default_tourism_slots(self) -> None:
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
                "pace": "balanced",
            }
        )

        tourism = [
            stop
            for stop in result["itinerary"]
            if stop["slot_kind"] == "tourism"
        ]
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["meta"]["places_per_day"], 3)
        self.assertEqual(len(tourism), 3)

    def test_full_regeneration_avoids_previous_places_when_possible(self) -> None:
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

        regenerated = orchestrator.revise(
            previous_result=original,
            message="일정이 마음에 들지 않으니 처음부터 다시 생성해 주세요.",
        )

        original_ids = {item["content_id"] for item in original["itinerary"]}
        regenerated_ids = {
            item["content_id"] for item in regenerated["itinerary"]
        }
        self.assertEqual(regenerated["status"], "completed")
        self.assertEqual(
            regenerated["meta"]["edit_mode"],
            "full_regeneration",
        )
        self.assertTrue(original_ids.isdisjoint(regenerated_ids))


if __name__ == "__main__":
    unittest.main()
