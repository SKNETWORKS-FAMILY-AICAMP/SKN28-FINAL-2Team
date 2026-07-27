from __future__ import annotations

import unittest

from src.rag.models import (
    PlaceSearchFilters,
    PlaceSearchResponse,
    RetrievedPlace,
    TravelConditions,
)
from src.rag.retrieval import (
    SlotRetriever,
    route_slots,
    select_route_context,
)


def place(
    content_id: int,
    *,
    latitude: float,
    longitude: float,
    similarity: float,
) -> RetrievedPlace:
    return RetrievedPlace(
        content_id=content_id,
        title=f"장소 {content_id}",
        latitude=latitude,
        longitude=longitude,
        similarity_score=similarity,
        rank=content_id,
        target_collection="attractions",
        itinerary_role="visit",
        tags=("nature",),
        opening_hours="09:00-18:00",
    )


class FakePlaceService:
    def __init__(self, places) -> None:
        self.places = tuple(places)

    def search_places(self, query, *, filters=None, **kwargs):
        return PlaceSearchResponse(
            query,
            filters or PlaceSearchFilters(),
            len(self.places),
            self.places,
        )


class SlotRetrievalTests(unittest.TestCase):
    def test_selects_complete_pattern_and_caps_it_to_pace_budget(self) -> None:
        def pattern(reference_id: str, counts: tuple[int, ...]):
            return {
                "reference_trip_id": reference_id,
                "match_score": 90,
                "days": [
                    {
                        "day": day,
                        "slots": [
                            {
                                "sequence": sequence,
                                "role": "visit",
                                "category": "nature",
                                "target_collections": ["attractions"],
                                "itinerary_roles": ["visit"],
                            }
                            for sequence in range(1, count + 1)
                        ],
                    }
                    for day, count in enumerate(counts, start=1)
                ],
            }

        selected = select_route_context(
            {
                "reference_trip_patterns": [
                    pattern("too-many", (7, 7, 6)),
                    pattern("right-sized", (4, 4, 4)),
                    pattern("too-short", (4, 4)),
                ]
            },
            duration_days=3,
            pace="relaxed",
        )

        self.assertEqual(
            selected["reference_trip_patterns"][0]["reference_trip_id"],
            "too-many",
        )
        slots = route_slots(
            selected,
            duration_days=3,
            max_slots_per_day=3,
        )
        self.assertEqual(len(slots), 9)
        self.assertEqual(
            [len([slot for slot in slots if slot.day == day]) for day in (1, 2, 3)],
            [3, 3, 3],
        )
        for day in (1, 2, 3):
            self.assertEqual(
                [slot.sequence for slot in slots if slot.day == day],
                [1, 2, 3],
            )

    def test_builds_slots_without_aihub_place_names(self) -> None:
        context = {
            "reference_trip_patterns": [
                {
                    "reference_trip_id": "aihub-trip:hash",
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
                                    "stay_minutes": 90,
                                    "location_hint": None,
                                }
                            ],
                        }
                    ],
                }
            ]
        }

        slots = route_slots(context, duration_days=1)

        self.assertEqual(len(slots), 1)
        self.assertEqual(slots[0].latitude, 33.45)
        self.assertEqual(slots[0].radius_km, 8.0)

    def test_filters_by_aihub_radius_and_scores_candidates(self) -> None:
        context = {
            "reference_trip_patterns": [
                {
                    "days": [
                        {
                            "day": 1,
                            "region": {
                                "center": {
                                    "latitude": 33.45,
                                    "longitude": 126.50,
                                },
                                "vector_search_radius_km": 10.0,
                            },
                            "slots": [
                                {
                                    "sequence": 1,
                                    "role": "visit",
                                    "category": "nature",
                                    "target_collections": ["attractions"],
                                    "itinerary_roles": ["visit"],
                                    "stay_minutes": 90,
                                }
                            ],
                        }
                    ]
                }
            ]
        }
        slot = route_slots(context, duration_days=1)[0]
        service = FakePlaceService(
            [
                place(
                    1,
                    latitude=33.451,
                    longitude=126.501,
                    similarity=0.8,
                ),
                place(
                    2,
                    latitude=33.20,
                    longitude=126.20,
                    similarity=0.95,
                ),
            ]
        )
        retriever = SlotRetriever(service, candidates_per_slot=5)
        conditions = TravelConditions.from_mapping(
            {
                "duration_days": 1,
                "party_type": "solo",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature"],
            }
        )

        result = retriever.retrieve(slot, conditions)

        self.assertEqual([item.content_id for item in result.candidates], [1])
        self.assertIsNotNone(result.candidates[0].slot_score)
        self.assertLess(result.candidates[0].distance_km or 100, 1)


if __name__ == "__main__":
    unittest.main()
