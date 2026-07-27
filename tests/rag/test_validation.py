from __future__ import annotations

import unittest

from src.rag.models import (
    ItineraryChoice,
    ItineraryDraft,
    RetrievedPlace,
    SlotCandidates,
    SlotRequest,
    TravelConditions,
)
from src.rag.validation import parse_opening_ranges, validate_and_schedule


def slot_result(
    *,
    day: int,
    sequence: int,
    content_id: int,
    title: str,
    latitude: float = 33.45,
    longitude: float = 126.50,
) -> SlotCandidates:
    slot = SlotRequest(
        day=day,
        sequence=sequence,
        role="visit",
        category="nature",
        target_collections=("attractions",),
        itinerary_roles=("visit",),
        stay_minutes=60,
        latitude=latitude,
        longitude=longitude,
        radius_km=10.0,
    )
    candidate = RetrievedPlace(
        content_id=content_id,
        title=title,
        latitude=latitude,
        longitude=longitude,
        similarity_score=0.9,
        rank=1,
        target_collection="attractions",
        itinerary_role="visit",
        opening_hours="09:00-18:00",
        slot_score=0.9,
    )
    return SlotCandidates(slot, "자연 관광지", (candidate,))


class ValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conditions = TravelConditions.from_mapping(
            {
                "duration_days": 1,
                "party_type": "solo",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature"],
            }
        )

    def test_parses_explicit_opening_range(self) -> None:
        self.assertEqual(parse_opening_ranges("매일 09:00~18:00"), ((540, 1080),))

    def test_accepts_whitelisted_place_and_builds_schedule(self) -> None:
        slots = [slot_result(day=1, sequence=1, content_id=101, title="숲")]
        draft = ItineraryDraft(
            (
                ItineraryChoice(
                    day=1,
                    slot_sequence=1,
                    content_id=101,
                    stay_minutes=60,
                    reason="자연 선호와 일치합니다.",
                ),
            )
        )

        result = validate_and_schedule(draft, slots, self.conditions)

        self.assertTrue(result.valid)
        self.assertEqual(result.schedule[0].start_time, "09:00")
        self.assertEqual(result.schedule[0].end_time, "10:00")

    def test_rejects_non_whitelisted_id(self) -> None:
        slots = [slot_result(day=1, sequence=1, content_id=101, title="숲")]
        draft = ItineraryDraft(
            (
                ItineraryChoice(
                    day=1,
                    slot_sequence=1,
                    content_id=999,
                    stay_minutes=60,
                    reason="잘못된 ID",
                ),
            )
        )

        result = validate_and_schedule(draft, slots, self.conditions)

        self.assertFalse(result.valid)
        self.assertIn("not_whitelisted", {issue.code for issue in result.issues})


if __name__ == "__main__":
    unittest.main()
