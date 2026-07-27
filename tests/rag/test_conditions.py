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
