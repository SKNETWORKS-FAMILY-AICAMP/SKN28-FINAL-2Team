from __future__ import annotations

import unittest

from src.rag.models import (
    PlaceSearchFilters,
    PlaceSearchResponse,
    RetrievedPlace,
    SlotRequest,
    TravelConditions,
)
from src.rag.retrieval import (
    SlotRetriever,
    add_meal_slots,
    build_slot_query,
    complete_route_slots,
    route_slots,
    score_slot_candidate,
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
    def test_adds_lunch_and_dinner_and_opt_in_breakfast(self) -> None:
        tourism = tuple(
            SlotRequest(
                day=1,
                sequence=sequence,
                role="visit",
                category="nature",
                target_collections=("attractions",),
                itinerary_roles=("visit",),
                stay_minutes=60,
                latitude=33.45 + sequence / 1000,
                longitude=126.50,
                radius_km=8.0,
            )
            for sequence in range(1, 4)
        )
        base = TravelConditions.from_mapping(
            {
                "duration_days": 1,
                "party_type": "solo",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature"],
            }
        )

        without_breakfast = add_meal_slots(tourism, base)
        with_breakfast = add_meal_slots(
            tourism,
            TravelConditions.from_mapping(
                {
                    **base.to_dict(),
                    "include_breakfast": True,
                    "meal_search_radius_km": 12,
                }
            ),
        )

        self.assertEqual(
            [slot.meal_type for slot in without_breakfast if slot.slot_kind == "meal"],
            ["lunch", "dinner"],
        )
        self.assertEqual(
            [slot.meal_type for slot in with_breakfast if slot.slot_kind == "meal"],
            ["breakfast", "lunch", "dinner"],
        )
        self.assertEqual(
            len([slot for slot in with_breakfast if slot.slot_kind == "tourism"]),
            3,
        )
        self.assertTrue(
            all(
                slot.radius_km == 12
                for slot in with_breakfast
                if slot.slot_kind == "meal"
            )
        )

        skip_lunch = add_meal_slots(
            tourism,
            TravelConditions.from_mapping(
                {
                    **base.to_dict(),
                    "skipped_meals": [
                        {"day": 1, "meal_type": "lunch"},
                    ],
                }
            ),
        )
        self.assertEqual(
            [
                slot.meal_type
                for slot in skip_lunch
                if slot.slot_kind == "meal"
            ],
            ["dinner"],
        )

    def test_meal_score_prioritizes_distance_rating_and_menu(self) -> None:
        slot = SlotRequest(
            day=1,
            sequence=102,
            role="meal",
            category="food_cafe",
            target_collections=("restaurants",),
            itinerary_roles=("meal",),
            stay_minutes=60,
            latitude=33.45,
            longitude=126.50,
            radius_km=8.0,
            slot_kind="meal",
            meal_type="lunch",
        )
        conditions = TravelConditions.from_mapping(
            {
                "duration_days": 1,
                "party_type": "solo",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature"],
                "preferred_foods": ["갈치조림"],
            }
        )
        preferred = RetrievedPlace(
            content_id=10,
            title="제주 갈치조림",
            latitude=33.45,
            longitude=126.50,
            similarity_score=0.8,
            rank=1,
            target_collection="restaurants",
            itinerary_role="meal",
            tags=("갈치조림",),
            opening_hours="10:00-21:00",
            rating=4.7,
        )
        weak = RetrievedPlace(
            content_id=11,
            title="먼 식당",
            latitude=33.45,
            longitude=126.50,
            similarity_score=0.8,
            rank=2,
            target_collection="restaurants",
            itinerary_role="meal",
            opening_hours="10:00-21:00",
        )

        strong_score, breakdown = score_slot_candidate(
            preferred, slot, conditions, distance_km=0.5
        )
        weak_score, weak_breakdown = score_slot_candidate(
            weak, slot, conditions, distance_km=7.5
        )

        self.assertGreater(strong_score, weak_score)
        self.assertEqual(breakdown["rating_available"], 1.0)
        self.assertEqual(weak_breakdown["rating_available"], 0.0)

    def test_filters_restaurant_closed_before_dinner(self) -> None:
        slot = SlotRequest(
            day=1,
            sequence=103,
            role="meal",
            category="food_cafe",
            target_collections=("restaurants",),
            itinerary_roles=("meal",),
            stay_minutes=70,
            latitude=33.45,
            longitude=126.50,
            radius_km=8.0,
            slot_kind="meal",
            meal_type="dinner",
        )
        restaurants = [
            RetrievedPlace(
                content_id=20,
                title="오후 영업 식당",
                latitude=33.45,
                longitude=126.50,
                similarity_score=0.95,
                rank=1,
                target_collection="restaurants",
                itinerary_role="meal",
                opening_hours="09:00-18:00",
            ),
            RetrievedPlace(
                content_id=21,
                title="저녁 영업 식당",
                latitude=33.451,
                longitude=126.501,
                similarity_score=0.8,
                rank=2,
                target_collection="restaurants",
                itinerary_role="meal",
                opening_hours="09:00-22:00",
            ),
        ]
        conditions = TravelConditions.from_mapping(
            {
                "duration_days": 1,
                "party_type": "solo",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature"],
            }
        )

        result = SlotRetriever(
            FakePlaceService(restaurants)
        ).retrieve(slot, conditions)

        self.assertEqual(
            [candidate.content_id for candidate in result.candidates],
            [21],
        )

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

    def test_fills_missing_day_from_previous_day_end_anchor(self) -> None:
        context = {
            "reference_trip_patterns": [
                {
                    "days": [
                        {
                            "day": day,
                            "region": {
                                "center": {
                                    "latitude": 33.40 + day / 100,
                                    "longitude": 126.50 + day / 100,
                                },
                                "vector_search_radius_km": 8.0,
                            },
                            "slots": [
                                {
                                    "sequence": sequence,
                                    "role": "visit",
                                    "category": "nature",
                                    "target_collections": ["attractions"],
                                    "itinerary_roles": ["visit"],
                                    "stay_minutes": 60,
                                }
                                for sequence in range(1, 4)
                            ],
                        }
                        for day in range(1, 4)
                    ]
                }
            ]
        }
        conditions = TravelConditions.from_mapping(
            {
                "duration_days": 4,
                "party_type": "non_family_two",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature", "culture"],
                "exit_point": "제주국제공항",
            }
        )
        original = route_slots(
            context,
            duration_days=4,
            max_slots_per_day=3,
        )

        completed = complete_route_slots(
            original,
            conditions,
            places_per_day=3,
            anchor_radius_km=20.0,
        )

        self.assertEqual(len(completed), 12)
        day_four = [slot for slot in completed if slot.day == 4]
        self.assertEqual(len(day_four), 3)
        self.assertTrue(
            all(slot.template_source == "synthetic_gap_fill" for slot in day_four)
        )
        self.assertEqual(day_four[0].latitude, original[-1].latitude)
        self.assertEqual(day_four[0].longitude, original[-1].longitude)
        self.assertEqual(day_four[-1].route_anchor, "제주국제공항")
        self.assertEqual(day_four[-1].target_collections, ("attractions",))
        self.assertEqual(day_four[-1].itinerary_roles, ("visit",))

    def test_retargets_aihub_food_slot_to_tourist_attraction(self) -> None:
        conditions = TravelConditions.from_mapping(
            {
                "duration_days": 1,
                "party_type": "solo",
                "local_transport": "rental_car",
                "preferred_visit_types": ["culture"],
            }
        )
        food_slot = SlotRequest(
            day=1,
            sequence=1,
            role="food",
            category="food_cafe",
            target_collections=("restaurants",),
            itinerary_roles=("meal", "cafe_break"),
            stay_minutes=60,
            latitude=33.45,
            longitude=126.50,
            radius_km=8.0,
        )

        completed = complete_route_slots(
            (food_slot,),
            conditions,
            places_per_day=1,
            anchor_radius_km=20.0,
        )

        self.assertEqual(completed[0].target_collections, ("attractions",))
        self.assertEqual(completed[0].itinerary_roles, ("visit",))
        self.assertEqual(completed[0].category, "culture")
        self.assertEqual(
            completed[0].template_source,
            "aihub_food_slot_retarget",
        )

    def test_adds_only_matching_day_required_places_to_query(self) -> None:
        conditions = TravelConditions.from_mapping(
            {
                "duration_days": 3,
                "party_type": "solo",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature"],
                "required_day_itineraries": [
                    {"day": 2, "place_names": ["우도"]},
                    {"day": 3, "place_names": ["한라수목원"]},
                ],
            }
        )
        slot = SlotRequest(
            day=2,
            sequence=1,
            role="visit",
            category="nature",
            target_collections=("attractions",),
            itinerary_roles=("visit",),
            stay_minutes=60,
            latitude=33.45,
            longitude=126.50,
            radius_km=8.0,
        )

        query = build_slot_query(slot, conditions)

        self.assertIn("우도", query)
        self.assertNotIn("한라수목원", query)

    def test_keeps_required_day_place_outside_aihub_radius(self) -> None:
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
                                "vector_search_radius_km": 5.0,
                            },
                            "slots": [
                                {
                                    "sequence": 1,
                                    "role": "visit",
                                    "category": "nature",
                                    "target_collections": ["attractions"],
                                    "itinerary_roles": ["visit"],
                                    "stay_minutes": 60,
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
                RetrievedPlace(
                    content_id=700,
                    title="우도",
                    latitude=33.50,
                    longitude=126.95,
                    similarity_score=0.99,
                    rank=1,
                    target_collection="attractions",
                    itinerary_role="visit",
                    tags=("nature",),
                    opening_hours="09:00-18:00",
                )
            ]
        )
        retriever = SlotRetriever(service)
        conditions = TravelConditions.from_mapping(
            {
                "duration_days": 1,
                "party_type": "solo",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature"],
                "required_day_itineraries": [
                    {"day": 1, "place_names": ["우도"]},
                ],
            }
        )

        result = retriever.retrieve(slot, conditions)

        self.assertEqual([place.title for place in result.candidates], ["우도"])


if __name__ == "__main__":
    unittest.main()
