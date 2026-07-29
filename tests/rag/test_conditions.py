from __future__ import annotations

import unittest

from src.rag.conditions import ConditionExtractionService
from src.rag.models import ItineraryDraft, TravelConditions


class FakeConditionLLM:
    def __init__(self, conditions: TravelConditions) -> None:
        self.conditions = conditions
        self.extract_calls = 0

    def extract_conditions(self, **kwargs):
        self.extract_calls += 1
        return self.conditions

    def generate_itinerary(self, context):
        return ItineraryDraft(())

    def repair_itinerary(self, **kwargs):
        return ItineraryDraft(())


class ConditionExtractionTests(unittest.TestCase):
    def test_menu_question_is_optional_and_disappears_after_selection(self) -> None:
        service = ConditionExtractionService(
            FakeConditionLLM(TravelConditions())
        )
        base = {
            "duration_days": 1,
            "party_type": "solo",
            "local_transport": "rental_car",
            "preferred_visit_types": ["nature"],
        }

        no_menu = service.from_selections(selected_options=base)
        with_menu = service.from_selections(
            selected_options={**base, "preferred_foods": ["흑돼지"]}
        )

        self.assertTrue(no_menu.ready)
        self.assertEqual(len(no_menu.optional_questions), 1)
        self.assertIn("메뉴", no_menu.optional_questions[0])
        self.assertEqual(with_menu.optional_questions, ())

    def test_breakfast_is_opt_in_condition(self) -> None:
        conditions = TravelConditions.from_mapping(
            {"include_breakfast": True}
        )

        self.assertTrue(conditions.include_breakfast)

    def test_accepts_selected_meal_search_radius(self) -> None:
        conditions = TravelConditions.from_mapping(
            {"meal_search_radius_km": 12}
        )

        self.assertEqual(conditions.meal_search_radius_km, 12)

        with self.assertRaisesRegex(ValueError, "between 1 and 30"):
            TravelConditions.from_mapping(
                {"meal_search_radius_km": 50}
            )

    def test_accepts_and_merges_skipped_meal_slots(self) -> None:
        service = ConditionExtractionService(
            FakeConditionLLM(TravelConditions())
        )
        current = {
            "duration_days": 2,
            "party_type": "solo",
            "local_transport": "rental_car",
            "preferred_visit_types": ["nature"],
            "skipped_meals": [
                {"day": 1, "meal_type": "dinner"},
            ],
        }

        result = service.from_selections(
            selected_options={
                "skipped_meals": [
                    {"day": 2, "meal_type": "lunch"},
                ]
            },
            current_conditions=current,
        )

        self.assertEqual(
            result.conditions.to_dict()["skipped_meals"],
            [
                {"day": 1, "meal_type": "dinner"},
                {"day": 2, "meal_type": "lunch"},
            ],
        )

    def test_frontend_selections_bypass_condition_llm(self) -> None:
        llm = FakeConditionLLM(TravelConditions())
        service = ConditionExtractionService(llm)

        result = service.from_selections(
            selected_options={
                "duration_days": 3,
                "party_type": "with_parents",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature", "culture"],
                "pace": "relaxed",
            }
        )

        self.assertTrue(result.ready)
        self.assertEqual(result.conditions.duration_days, 3)
        self.assertEqual(llm.extract_calls, 0)

    def test_accepts_optional_route_and_required_itinerary_selections(self) -> None:
        llm = FakeConditionLLM(TravelConditions())
        service = ConditionExtractionService(llm)

        result = service.from_selections(
            selected_options={
                "duration_days": 4,
                "party_type": "non_family_two",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature", "culture"],
                "start_point": "제주국제공항",
                "end_point": "제주항",
                "required_itinerary": ["성산일출봉", "우도"],
                "accommodation": "서귀포시 중문동 숙소",
            }
        )

        self.assertTrue(result.ready)
        self.assertEqual(result.conditions.entry_point, "제주국제공항")
        self.assertEqual(result.conditions.exit_point, "제주항")
        self.assertEqual(
            result.conditions.must_visit_places,
            ("성산일출봉", "우도"),
        )
        self.assertEqual(
            result.conditions.accommodation_address,
            "서귀포시 중문동 숙소",
        )
        self.assertEqual(llm.extract_calls, 0)

    def test_optional_route_fields_do_not_trigger_clarification(self) -> None:
        service = ConditionExtractionService(
            FakeConditionLLM(
                TravelConditions.from_mapping(
                    {
                        "duration_days": 2,
                        "party_type": "solo",
                        "local_transport": "public_transit",
                        "preferred_visit_types": ["history"],
                    }
                )
            )
        )

        result = service.extract(message="선택 조건 없이 기본 일정")

        self.assertTrue(result.ready)
        self.assertIsNone(result.conditions.entry_point)
        self.assertIsNone(result.conditions.exit_point)
        self.assertIsNone(result.conditions.accommodation_address)
        self.assertEqual(result.conditions.must_visit_places, ())

    def test_accepts_optional_trip_start_and_airport_deadline(self) -> None:
        llm = FakeConditionLLM(TravelConditions())
        service = ConditionExtractionService(llm)

        result = service.from_selections(
            selected_options={
                "duration_days": 3,
                "party_type": "non_family_two",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature"],
                "trip_start_time": "10:00",
                "departure_airport": "제주국제공항",
                "airport_arrival_deadline": "16:00",
            }
        )

        self.assertTrue(result.ready)
        self.assertEqual(result.conditions.arrival_time, "10:00")
        self.assertEqual(result.conditions.exit_point, "제주국제공항")
        self.assertEqual(result.conditions.departure_time, "16:00")

    def test_asks_airport_only_when_deadline_has_no_airport(self) -> None:
        llm = FakeConditionLLM(TravelConditions())
        service = ConditionExtractionService(llm)

        result = service.from_selections(
            selected_options={
                "duration_days": 3,
                "party_type": "solo",
                "local_transport": "public_transit",
                "preferred_visit_types": ["history"],
                "airport_arrival_deadline": "17:00",
            }
        )

        self.assertFalse(result.ready)
        self.assertEqual(
            result.conditions.missing_conditional_fields(),
            ("departure_airport",),
        )
        self.assertEqual(len(result.clarification_questions), 1)
        self.assertIn("공항", result.clarification_questions[0])

    def test_rejects_invalid_optional_time_format(self) -> None:
        with self.assertRaisesRegex(ValueError, "HH:MM"):
            TravelConditions.from_mapping(
                {
                    "trip_start_time": "오전 10시",
                }
            )

    def test_accepts_and_merges_required_itineraries_by_day(self) -> None:
        llm = FakeConditionLLM(
            TravelConditions.from_mapping(
                {
                    "required_day_itineraries": [
                        {"day": 2, "place_names": ["성산일출봉"]},
                        {"day": 3, "place_names": ["한라수목원"]},
                    ]
                }
            )
        )
        service = ConditionExtractionService(llm)

        result = service.extract(
            message="2일차에 성산일출봉도 추가해 주세요",
            current_conditions={
                "duration_days": 3,
                "party_type": "non_family_two",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature"],
                "must_visit_by_day": {"2": ["우도"]},
            },
        )

        self.assertTrue(result.ready)
        self.assertEqual(
            result.conditions.to_dict()["required_day_itineraries"],
            [
                {
                    "day": 2,
                    "place_names": ["우도", "성산일출봉"],
                },
                {"day": 3, "place_names": ["한라수목원"]},
            ],
        )
        self.assertEqual(result.conditions.must_visit_places, ())

    def test_removes_day_specific_place_from_global_must_visit(self) -> None:
        service = ConditionExtractionService(
            FakeConditionLLM(
                TravelConditions.from_mapping(
                    {
                        "duration_days": 2,
                        "party_type": "solo",
                        "local_transport": "rental_car",
                        "preferred_visit_types": ["nature"],
                        "must_visit_places": ["우도"],
                        "required_day_itineraries": [
                            {"day": 2, "place_names": ["우도"]},
                        ],
                    }
                )
            )
        )

        result = service.extract(message="2일차 우도 필수")

        self.assertTrue(result.ready)
        self.assertEqual(result.conditions.must_visit_places, ())
        self.assertEqual(
            result.conditions.required_day_itineraries[0].place_names,
            ("우도",),
        )

    def test_rejects_required_day_after_trip_duration(self) -> None:
        with self.assertRaisesRegex(ValueError, "exceeds duration_days"):
            TravelConditions.from_mapping(
                {
                    "duration_days": 2,
                    "required_day_itineraries": [
                        {"day": 3, "place_names": ["우도"]},
                    ],
                }
            )

    def test_returns_questions_for_missing_aihub_fields(self) -> None:
        service = ConditionExtractionService(
            FakeConditionLLM(
                TravelConditions.from_mapping(
                    {
                        "duration_days": 3,
                        "party_type": "with_parents",
                    }
                )
            )
        )

        result = service.extract(message="부모님과 3일 여행할래요")

        self.assertFalse(result.ready)
        self.assertEqual(
            result.conditions.missing_required_fields(),
            ("local_transport", "preferred_visit_types"),
        )
        self.assertEqual(len(result.clarification_questions), 2)

    def test_merges_previous_conditions_and_removes_exclusion_conflict(self) -> None:
        service = ConditionExtractionService(
            FakeConditionLLM(
                TravelConditions.from_mapping(
                    {
                        "preferred_visit_types": ["nature"],
                        "must_visit_places": ["성산일출봉"],
                        "excluded_places": ["성산일출봉", "카페"],
                    }
                )
            )
        )
        current = {
            "duration_days": 3,
            "party_type": "with_parents",
            "local_transport": "rental_car",
        }

        result = service.extract(
            message="자연 위주로, 성산일출봉은 꼭 넣고 카페는 빼주세요",
            current_conditions=current,
        )

        self.assertTrue(result.ready)
        self.assertEqual(result.conditions.must_visit_places, ("성산일출봉",))
        self.assertEqual(result.conditions.excluded_places, ("카페",))

    def test_preserves_detailed_preferences_and_exclusion_priority(self) -> None:
        service = ConditionExtractionService(
            FakeConditionLLM(
                TravelConditions.from_mapping(
                    {
                        "region": "제주",
                        "start_date": "2026-08-10",
                        "end_date": "2026-08-12",
                        "duration_days": 3,
                        "party_type": "with_parents",
                        "local_transport": "rental_car",
                        "preferred_visit_types": ["nature"],
                        "preferred_foods": ["해산물", "흑돼지"],
                        "excluded_foods": ["흑돼지"],
                        "avoid_long_distance": True,
                        "parking_required": True,
                        "indoor_preference": "indoor",
                    }
                )
            )
        )

        result = service.extract(message="상세 여행 조건")

        self.assertTrue(result.ready)
        self.assertEqual(result.conditions.preferred_foods, ("해산물",))
        self.assertTrue(result.conditions.avoid_long_distance)
        self.assertTrue(result.conditions.parking_required)
        self.assertEqual(result.conditions.indoor_preference, "indoor")


if __name__ == "__main__":
    unittest.main()
