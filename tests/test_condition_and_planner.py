from __future__ import annotations

import unittest

from src.models.travel_condition import (
    ConditionDelta,
    LocalTransport,
    Pace,
    PartyType,
    SlotAddRequest,
    TravelCondition,
    VisitPreference,
    apply_delta,
    infer_affected_slots,
    summarize_trip_title,
)
from src.planner.config import PlannerConfig
from src.planner.planner import select_candidates
from src.rag.models import RetrievedPlace


def _condition(**overrides) -> TravelCondition:
    values = {
        "duration_days": 2,
        "party_type": PartyType.SOLO,
        "local_transport": LocalTransport.RENTAL_CAR,
        "preferred_visit_types": (VisitPreference.NATURE,),
        "companion_count": 1,
    }
    values.update(overrides)
    return TravelCondition(**values)


def _place(
    content_id: int,
    title: str,
    *,
    similarity: float = 0.5,
    latitude: float | None = 33.5,
    longitude: float | None = 126.5,
    tags: tuple[str, ...] = (),
    overview: str | None = None,
) -> RetrievedPlace:
    return RetrievedPlace(
        content_id=content_id,
        title=title,
        similarity_score=similarity,
        latitude=latitude,
        longitude=longitude,
        tags=tags,
        overview=overview,
    )


class TravelConditionTests(unittest.TestCase):
    def test_from_mapping_converts_enums_and_defaults_companion_count(self) -> None:
        condition = TravelCondition.from_mapping(
            {
                "duration_days": "3",
                "party_type": "solo",
                "local_transport": "public_transit",
                "preferred_visit_types": ["nature"],
            }
        )

        self.assertEqual(condition.duration_days, 3)
        self.assertEqual(condition.local_transport, LocalTransport.PUBLIC_TRANSIT)
        self.assertEqual(condition.preferred_visit_types, (VisitPreference.NATURE,))
        self.assertIsNone(condition.companion_count)

    def test_summarize_trip_title_uses_condition_instead_of_raw_request(self) -> None:
        condition = _condition(
            duration_days=3,
            party_type=PartyType.WITH_CHILDREN,
            preferred_visit_types=(VisitPreference.NATURE, VisitPreference.FOOD_CAFE),
        )

        self.assertEqual(
            summarize_trip_title(condition),
            "2박 3일 아이와 가족 자연·맛집 여행",
        )

    def test_slot_add_request_rejects_role_and_clamps_count(self) -> None:
        self.assertIsNone(SlotAddRequest.from_mapping({"role": "hotel"}))
        self.assertEqual(
            SlotAddRequest.from_mapping({"role": "food", "count": 100}).count,
            10,
        )
        self.assertEqual(
            SlotAddRequest.from_mapping({"role": "food", "count": -2}).count,
            1,
        )

    def test_condition_delta_ignores_invalid_preferences_and_slots(self) -> None:
        delta = ConditionDelta.from_mapping(
            {
                "add_preferred_visit_types": ["nature", "invalid"],
                "add_slots": [
                    {"role": "activity", "day": 2, "count": 2},
                    {"role": "hotel", "count": 1},
                    "invalid",
                ],
            }
        )

        self.assertEqual(delta.add_preferred_visit_types, (VisitPreference.NATURE,))
        self.assertEqual(delta.add_slots, (SlotAddRequest("activity", 2, 2),))

    def test_apply_delta_resolves_must_visit_exclusion_conflict(self) -> None:
        condition = _condition(must_visit_places=("우도", "성산일출봉"))
        delta = ConditionDelta(
            add_must_visit_places=("협재해변",),
            add_excluded_places=("우도", "협재해변"),
            remove_must_visit_places=("성산일출봉",),
        )

        updated = apply_delta(condition, delta)

        self.assertEqual(updated.must_visit_places, ())
        self.assertEqual(updated.excluded_places, ("우도", "협재해변"))

    def test_apply_delta_keeps_existing_preference_when_all_removed(self) -> None:
        condition = _condition()
        updated = apply_delta(
            condition,
            ConditionDelta(remove_preferred_visit_types=(VisitPreference.NATURE,)),
        )
        self.assertEqual(updated.preferred_visit_types, (VisitPreference.NATURE,))

    def test_infer_affected_slots_honors_explicit_order_without_duplicates(self) -> None:
        delta = ConditionDelta(affected_slots=("food", "visit", "food"))
        self.assertEqual(infer_affected_slots(delta), ("food", "visit"))

    def test_add_slots_does_not_refresh_existing_slots(self) -> None:
        delta = ConditionDelta(add_slots=(SlotAddRequest("food"),))
        self.assertEqual(infer_affected_slots(delta), ())

    def test_remove_places_does_not_create_replacement_slots(self) -> None:
        delta = ConditionDelta.from_mapping({"remove_places": ["우도"]})

        self.assertEqual(delta.remove_places, ("우도",))
        self.assertEqual(infer_affected_slots(delta), ())
        self.assertIn("우도", apply_delta(_condition(), delta).excluded_places)

    def test_unstructured_delta_refreshes_all_slots(self) -> None:
        self.assertEqual(
            infer_affected_slots(ConditionDelta(notes="조금 더 여유롭게")),
            ("visit", "activity", "food", "shopping"),
        )


class PlannerTests(unittest.TestCase):
    def test_style_keywords_affect_ranking(self) -> None:
        config = PlannerConfig(
            similarity_weight=0.0,
            proximity_weight=0.0,
            style_weight=1.0,
        )
        candidates = select_candidates(
            [_place(1, "도심 전시관"), _place(2, "숲길 산책", tags=("자연",))],
            _condition(),
            role="visit",
            config=config,
        )
        self.assertEqual(candidates[0].content_id, 2)

    def test_excluded_id_and_title_are_filtered(self) -> None:
        candidates = select_candidates(
            [_place(1, "우도 해변"), _place(2, "협재 해변"), _place(3, "오름")],
            _condition(excluded_places=("우도",)),
            role="visit",
            exclude_content_ids={2},
        )
        self.assertEqual([candidate.content_id for candidate in candidates], [3])

    def test_public_transit_radius_filters_far_place(self) -> None:
        candidates = select_candidates(
            [
                _place(1, "제주 근처"),
                _place(2, "서울", latitude=37.5665, longitude=126.9780),
            ],
            _condition(local_transport=LocalTransport.PUBLIC_TRANSIT),
            role="visit",
            location_hint={"latitude": 33.5, "longitude": 126.5},
        )
        self.assertEqual([candidate.content_id for candidate in candidates], [1])

    def test_same_normalized_title_keeps_higher_similarity(self) -> None:
        candidates = select_candidates(
            [_place(1, "성산 일출봉", similarity=0.2), _place(2, "성산일출봉", similarity=0.9)],
            _condition(),
            role="visit",
        )
        self.assertEqual([candidate.content_id for candidate in candidates], [2])

    def test_role_default_limit_is_applied(self) -> None:
        candidates = select_candidates(
            [_place(index, f"식당 {index}", similarity=index / 10) for index in range(1, 6)],
            _condition(preferred_visit_types=(VisitPreference.FOOD_CAFE,)),
            role="food",
        )
        self.assertEqual(len(candidates), 2)
        self.assertEqual([candidate.content_id for candidate in candidates], [5, 4])


if __name__ == "__main__":
    unittest.main()
