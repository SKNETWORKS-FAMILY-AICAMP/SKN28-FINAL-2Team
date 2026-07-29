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
from src.rag.validation import (
    deterministic_draft,
    parse_opening_ranges,
    validate_and_schedule,
)


def slot_result(
    *,
    day: int,
    sequence: int,
    content_id: int,
    title: str,
    latitude: float = 33.45,
    longitude: float = 126.50,
    target_collection: str = "attractions",
    itinerary_role: str = "visit",
    opening_hours: str = "09:00-18:00",
    slot_kind: str = "tourism",
    meal_type: str | None = None,
    stay_minutes: int = 60,
    overview: str = "",
) -> SlotCandidates:
    slot = SlotRequest(
        day=day,
        sequence=sequence,
        role="visit",
        category="nature",
        target_collections=(target_collection,),
        itinerary_roles=(itinerary_role,),
        stay_minutes=stay_minutes,
        latitude=latitude,
        longitude=longitude,
        radius_km=10.0,
        slot_kind=slot_kind,
        meal_type=meal_type,
    )
    candidate = RetrievedPlace(
        content_id=content_id,
        title=title,
        latitude=latitude,
        longitude=longitude,
        similarity_score=0.9,
        rank=1,
        target_collection=target_collection,
        itinerary_role=itinerary_role,
        opening_hours=opening_hours,
        overview=overview,
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
        slots = [
            slot_result(
                day=1,
                sequence=1,
                content_id=101,
                title="숲",
                overview=(
                    "제주의 자연을 가까이에서 만날 수 있는 숲길입니다. "
                    "완만한 산책 구간이 마련되어 있습니다. "
                    "이 문장은 두 문장 제한으로 제외됩니다."
                ),
            )
        ]
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
        payload = result.schedule[0].to_dict()
        self.assertEqual(
            payload["description"],
            (
                "제주의 자연을 가까이에서 만날 수 있는 숲길입니다. "
                "완만한 산책 구간이 마련되어 있습니다."
            ),
        )
        self.assertEqual(payload["selection_reason"], payload["reason"])

    def test_deterministic_choice_explains_user_condition(self) -> None:
        slots = [
            slot_result(
                day=1,
                sequence=1,
                content_id=201,
                title="제주 숲길",
                overview="제주의 숲을 따라 걷는 자연 관광지입니다.",
            )
        ]

        draft = deterministic_draft(slots, self.conditions)
        result = validate_and_schedule(draft, slots, self.conditions)

        self.assertTrue(result.valid)
        self.assertIn("자연 선호", result.schedule[0].reason)
        self.assertIn("제주 숲길:", result.schedule[0].reason)
        self.assertEqual(
            result.schedule[0].description,
            "제주의 숲을 따라 걷는 자연 관광지입니다.",
        )

    def test_deterministic_draft_reserves_scarce_future_candidate(self) -> None:
        shared = RetrievedPlace(
            content_id=701,
            title="공통 후보",
            latitude=33.45,
            longitude=126.50,
            similarity_score=0.95,
            rank=1,
            target_collection="attractions",
            itinerary_role="visit",
            opening_hours="09:00-18:00",
            slot_score=0.95,
        )
        alternative = RetrievedPlace(
            content_id=702,
            title="첫 슬롯 대체 후보",
            latitude=33.451,
            longitude=126.501,
            similarity_score=0.8,
            rank=2,
            target_collection="attractions",
            itinerary_role="visit",
            opening_hours="09:00-18:00",
            slot_score=0.8,
        )
        first = slot_result(
            day=1,
            sequence=1,
            content_id=701,
            title="공통 후보",
        )
        first = SlotCandidates(
            first.slot,
            first.query,
            (shared, alternative),
        )
        second = slot_result(
            day=1,
            sequence=2,
            content_id=701,
            title="공통 후보",
        )

        draft = deterministic_draft(
            (first, second),
            self.conditions,
        )

        self.assertEqual(
            [choice.content_id for choice in draft.choices],
            [702, 701],
        )

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

    def test_spreads_three_places_around_meal_breaks(self) -> None:
        slots = [
            slot_result(
                day=1,
                sequence=sequence,
                content_id=100 + sequence,
                title=f"관광지 {sequence}",
            )
            for sequence in range(1, 4)
        ]
        draft = ItineraryDraft(
            tuple(
                ItineraryChoice(
                    day=1,
                    slot_sequence=sequence,
                    content_id=100 + sequence,
                    stay_minutes=60,
                    reason="시간대별 관광지입니다.",
                )
                for sequence in range(1, 4)
            )
        )

        result = validate_and_schedule(draft, slots, self.conditions)

        self.assertTrue(result.valid)
        self.assertEqual(
            [stop.start_time for stop in result.schedule],
            ["09:00", "13:00", "15:30"],
        )
        self.assertEqual(
            [stop.end_time for stop in result.schedule],
            ["10:00", "14:00", "16:30"],
        )

    def test_schedules_separate_lunch_and_dinner_restaurants(self) -> None:
        slots = [
            slot_result(
                day=1,
                sequence=1,
                content_id=101,
                title="오전 관광지",
            ),
            slot_result(
                day=1,
                sequence=102,
                content_id=201,
                title="점심 식당",
                target_collection="restaurants",
                itinerary_role="meal",
                opening_hours="11:00-21:00",
                slot_kind="meal",
                meal_type="lunch",
            ),
            slot_result(
                day=1,
                sequence=2,
                content_id=102,
                title="오후 관광지",
            ),
            slot_result(
                day=1,
                sequence=3,
                content_id=103,
                title="저녁 전 관광지",
            ),
            slot_result(
                day=1,
                sequence=103,
                content_id=202,
                title="저녁 식당",
                target_collection="restaurants",
                itinerary_role="meal",
                opening_hours="11:00-22:00",
                slot_kind="meal",
                meal_type="dinner",
                stay_minutes=70,
            ),
        ]
        draft = ItineraryDraft(
            tuple(
                ItineraryChoice(
                    day=1,
                    slot_sequence=item.slot.sequence,
                    content_id=item.candidates[0].content_id,
                    stay_minutes=item.slot.stay_minutes or 60,
                    reason="시간대와 동선을 반영했습니다.",
                )
                for item in slots
            )
        )

        result = validate_and_schedule(draft, slots, self.conditions)

        self.assertTrue(result.valid)
        self.assertEqual(
            [stop.sequence for stop in result.schedule],
            [1, 102, 2, 3, 103],
        )
        self.assertEqual(result.schedule[1].start_time, "12:00")
        self.assertEqual(result.schedule[-1].start_time, "18:00")
        self.assertEqual(result.schedule[1].meal_type, "lunch")
        self.assertEqual(result.schedule[-1].meal_type, "dinner")

    def test_schedules_breakfast_only_when_slot_is_present(self) -> None:
        conditions = TravelConditions.from_mapping(
            {**self.conditions.to_dict(), "include_breakfast": True}
        )
        slots = [
            slot_result(
                day=1,
                sequence=101,
                content_id=210,
                title="아침 식당",
                target_collection="restaurants",
                itinerary_role="meal",
                opening_hours="07:00-11:00",
                slot_kind="meal",
                meal_type="breakfast",
                stay_minutes=50,
            ),
            slot_result(
                day=1,
                sequence=1,
                content_id=110,
                title="오전 관광지",
            ),
        ]
        draft = ItineraryDraft(
            tuple(
                ItineraryChoice(
                    day=1,
                    slot_sequence=item.slot.sequence,
                    content_id=item.candidates[0].content_id,
                    stay_minutes=item.slot.stay_minutes or 60,
                    reason="아침식사 요청을 반영했습니다.",
                )
                for item in slots
            )
        )

        result = validate_and_schedule(draft, slots, conditions)

        self.assertTrue(result.valid)
        self.assertEqual(result.schedule[0].meal_type, "breakfast")
        self.assertEqual(result.schedule[0].start_time, "07:30")
        self.assertEqual(result.schedule[1].start_time, "09:00")

    def test_rejects_restaurant_or_cafe_as_tour_place(self) -> None:
        slots = [
            slot_result(
                day=1,
                sequence=1,
                content_id=201,
                title="테스트 음식점",
                target_collection="restaurants",
                itinerary_role="meal",
            )
        ]
        draft = ItineraryDraft(
            (
                ItineraryChoice(
                    day=1,
                    slot_sequence=1,
                    content_id=201,
                    stay_minutes=60,
                    reason="음식점 후보",
                ),
            )
        )

        result = validate_and_schedule(draft, slots, self.conditions)

        self.assertFalse(result.valid)
        self.assertIn(
            "food_or_cafe_not_allowed",
            {issue.code for issue in result.issues},
        )

    def test_uses_jeju_airport_as_first_route_anchor(self) -> None:
        conditions = TravelConditions.from_mapping(
            {
                **self.conditions.to_dict(),
                "entry_point": "제주국제공항",
            }
        )
        slots = [
            slot_result(
                day=1,
                sequence=1,
                content_id=301,
                title="공항 인근 관광지",
                latitude=33.48,
                longitude=126.51,
            )
        ]
        draft = ItineraryDraft(
            (
                ItineraryChoice(
                    day=1,
                    slot_sequence=1,
                    content_id=301,
                    stay_minutes=60,
                    reason="공항에서 출발합니다.",
                ),
            )
        )

        result = validate_and_schedule(draft, slots, conditions)

        self.assertTrue(result.valid)
        self.assertGreater(result.schedule[0].start_time, "09:00")
        self.assertIsNotNone(result.schedule[0].distance_from_previous_km)

    def test_honors_optional_trip_start_time(self) -> None:
        conditions = TravelConditions.from_mapping(
            {
                **self.conditions.to_dict(),
                "trip_start_time": "10:00",
            }
        )
        slots = [
            slot_result(
                day=1,
                sequence=1,
                content_id=401,
                title="오전 관광지",
            )
        ]
        draft = ItineraryDraft(
            (
                ItineraryChoice(
                    day=1,
                    slot_sequence=1,
                    content_id=401,
                    stay_minutes=60,
                    reason="사용자 시작시각을 반영합니다.",
                ),
            )
        )

        result = validate_and_schedule(draft, slots, conditions)

        self.assertTrue(result.valid)
        self.assertEqual(result.schedule[0].start_time, "10:00")

    def test_rejects_route_that_misses_airport_arrival_deadline(self) -> None:
        conditions = TravelConditions.from_mapping(
            {
                **self.conditions.to_dict(),
                "departure_airport": "제주국제공항",
                "airport_arrival_deadline": "16:20",
            }
        )
        slots = [
            slot_result(
                day=1,
                sequence=sequence,
                content_id=500 + sequence,
                title=f"관광지 {sequence}",
                latitude=33.25,
                longitude=126.55,
            )
            for sequence in range(1, 4)
        ]
        draft = ItineraryDraft(
            tuple(
                ItineraryChoice(
                    day=1,
                    slot_sequence=sequence,
                    content_id=500 + sequence,
                    stay_minutes=30,
                    reason="공항 제한시각 검증 일정입니다.",
                )
                for sequence in range(1, 4)
            )
        )

        result = validate_and_schedule(draft, slots, conditions)

        self.assertFalse(result.valid)
        self.assertIn(
            "destination_time_limit",
            {issue.code for issue in result.issues},
        )

    def test_requires_place_on_the_specified_day(self) -> None:
        conditions = TravelConditions.from_mapping(
            {
                "duration_days": 2,
                "party_type": "solo",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature"],
                "required_day_itineraries": [
                    {"day": 2, "place_names": ["우도"]},
                ],
            }
        )
        wrong_day_slots = [
            slot_result(
                day=1,
                sequence=1,
                content_id=601,
                title="우도",
            ),
            slot_result(
                day=2,
                sequence=1,
                content_id=602,
                title="다른 관광지",
            ),
        ]
        wrong_day_draft = ItineraryDraft(
            (
                ItineraryChoice(1, 1, 601, 60, "우도를 잘못된 날에 배치"),
                ItineraryChoice(2, 1, 602, 60, "둘째 날 다른 장소"),
            )
        )

        failed = validate_and_schedule(
            wrong_day_draft,
            wrong_day_slots,
            conditions,
        )

        self.assertFalse(failed.valid)
        self.assertIn(
            "missing_required_day_place",
            {issue.code for issue in failed.issues},
        )

        correct_day_slots = [
            slot_result(
                day=1,
                sequence=1,
                content_id=603,
                title="다른 관광지",
            ),
            slot_result(
                day=2,
                sequence=1,
                content_id=604,
                title="우도",
            ),
        ]
        correct_day_draft = ItineraryDraft(
            (
                ItineraryChoice(1, 1, 603, 60, "첫째 날 관광지"),
                ItineraryChoice(2, 1, 604, 60, "둘째 날 우도"),
            )
        )

        completed = validate_and_schedule(
            correct_day_draft,
            correct_day_slots,
            conditions,
        )

        self.assertTrue(completed.valid)


if __name__ == "__main__":
    unittest.main()
