from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import unittest

from src.engine import (
    AppContainer,
    ItineraryEngine,
    _default_day_structure,
    _parse_position_delete_request,
)
from src.models.travel_condition import (
    ConditionDelta,
    LocalTransport,
    PartyType,
    TravelCondition,
    VisitPreference,
)
from src.planner.config import PlannerConfig
from src.rag.models import PlaceSearchFilters, PlaceSearchResponse, RetrievedPlace


def _condition() -> TravelCondition:
    return TravelCondition(
        duration_days=1,
        party_type=PartyType.SOLO,
        local_transport=LocalTransport.RENTAL_CAR,
        preferred_visit_types=(VisitPreference.NATURE,),
        companion_count=1,
    )


def _place(content_id: int, title: str, collection: str) -> RetrievedPlace:
    return RetrievedPlace(
        content_id=content_id,
        title=title,
        similarity_score=1.0 - content_id / 100,
        latitude=33.5,
        longitude=126.5,
        tags=(f"target_collection:{collection}",),
    )


class FakePatternRepository:
    def __init__(self) -> None:
        self.route_calls = []

    def fetch_trip_routes(self, travel_ids):
        self.route_calls.append(list(travel_ids))
        return []


class FakePatternService:
    def __init__(self) -> None:
        self.repository = FakePatternRepository()

    def find_reference_trips(self, condition):
        return []

    def find_reference_keyword_trips(self, condition):
        raise AssertionError("keyword lookup must be skipped when no reference trip exists")


class FakeRetrievalService:
    def __init__(self, places) -> None:
        self.places = tuple(places)
        self.calls = []

    def search_places(self, query, *, filters=None, top_k=8):
        self.calls.append((query, filters, top_k))
        return PlaceSearchResponse(
            query=query,
            filters=filters or PlaceSearchFilters(),
            top_k=top_k,
            places=self.places,
        )


class FakeLLMService:
    def __init__(self, condition) -> None:
        self.condition = condition
        self.delta = ConditionDelta()
        self.generated_days = None
        self.revision_calls = []

    def extract_travel_condition(self, user_text):
        return self.condition

    def generate_style_query(self, condition, *, reference_keywords=None):
        return "제주 자연 여행"

    def generate_search_query(self, condition, *, slot_role, day, extra_request=None):
        return f"{slot_role} 검색"

    def generate_itinerary(self, condition, days_with_candidates, *, movement_patterns=None):
        self.generated_days = days_with_candidates
        return {
            "days": [
                {
                    "day": day["day"],
                    "stops": [
                        {
                            "sequence": slot["sequence"],
                            "role": slot["role"],
                            "content_id": slot["candidates"][0]["content_id"],
                            "title": slot["candidates"][0]["title"],
                        }
                        for slot in day["slots"]
                    ],
                }
                for day in days_with_candidates
            ]
        }

    def extract_condition_delta(self, condition, user_text):
        return self.delta

    def revise_itinerary(self, condition, existing, changed_slots):
        self.revision_calls.append(changed_slots)
        return existing


class ItineraryEngineTests(unittest.TestCase):
    def _engine(self):
        condition = _condition()
        llm = FakeLLMService(condition)
        retrieval = FakeRetrievalService(
            [
                _place(1, "협재해변", "attractions"),
                _place(2, "성산일출봉", "attractions"),
                _place(3, "카약", "activities"),
                _place(4, "식당 A", "restaurants"),
                _place(5, "식당 B", "restaurants"),
            ]
        )
        config = PlannerConfig(slot_limits={"visit": 1, "activity": 1, "food": 1})
        engine = ItineraryEngine(
            AppContainer(
                retrieval_service=retrieval,
                pattern_service=FakePatternService(),
                llm_service=llm,
                planner_config=config,
            )
        )
        return engine, llm, retrieval

    def test_create_itinerary_fills_fixed_slots_from_unique_rag_candidates(self) -> None:
        engine, llm, retrieval = self._engine()

        with redirect_stdout(StringIO()):
            state = engine.create_itinerary("혼자 제주 자연 여행")

        self.assertEqual(len(state.slots), 5)
        self.assertTrue(all(len(slot.candidates) == 1 for slot in state.slots))
        selected_ids = [slot.candidates[0].content_id for slot in state.slots]
        self.assertEqual(len(selected_ids), len(set(selected_ids)))
        self.assertEqual(state.used_content_ids, {1, 2, 3, 4, 5})
        self.assertEqual(len(llm.generated_days), 1)
        self.assertEqual(len(llm.generated_days[0]["slots"]), 5)
        self.assertEqual(len(retrieval.calls), 1)

    def test_empty_delta_returns_existing_schedule_without_revision(self) -> None:
        engine, llm, _ = self._engine()
        with redirect_stdout(StringIO()):
            state = engine.create_itinerary("여행")
            updated = engine.update_itinerary_from_chat(state, "그대로")

        self.assertIs(updated.slots, state.slots)
        self.assertIs(updated.itinerary, state.itinerary)
        self.assertEqual(llm.revision_calls, [])

    def test_default_day_structure_has_five_ordered_slots_per_day(self) -> None:
        condition = _condition()
        condition = TravelCondition.from_mapping(
            {**condition.to_llm_dict(), "duration_days": 2}
        )
        days = _default_day_structure(condition)
        self.assertEqual([day["day"] for day in days], [1, 2])
        self.assertTrue(all(day["slot_count"] == 5 for day in days))
        self.assertEqual(
            [slot["role"] for slot in days[0]["slots"]],
            ["visit", "activity", "food", "visit", "food"],
        )

    def test_remove_place_deletes_stop_and_slot_without_replacement(self) -> None:
        engine, llm, _ = self._engine()
        with redirect_stdout(StringIO()):
            state = engine.create_itinerary("여행")

        removed_title = state.itinerary["days"][0]["stops"][0]["title"]
        removed_content_id = state.itinerary["days"][0]["stops"][0]["content_id"]
        llm.delta = ConditionDelta(remove_places=(removed_title,))

        with redirect_stdout(StringIO()):
            updated = engine.update_itinerary_from_chat(
                state,
                f"{removed_title} 삭제해줘",
            )

        self.assertEqual(len(updated.itinerary["days"][0]["stops"]), 4)
        self.assertEqual(len(updated.slots), 4)
        self.assertEqual(
            [stop["sequence"] for stop in updated.itinerary["days"][0]["stops"]],
            [1, 2, 3, 4],
        )
        self.assertEqual([slot.sequence for slot in updated.slots], [1, 2, 3, 4])
        self.assertNotIn(removed_content_id, updated.used_content_ids)
        self.assertIn(removed_title, updated.condition.excluded_places)
        self.assertEqual(llm.revision_calls, [])

    def test_position_delete_removes_requested_schedule_item(self) -> None:
        self.assertEqual(
            _parse_position_delete_request("2째날 3번째 일정을 지워줘"),
            (2, 3),
        )
        self.assertEqual(
            _parse_position_delete_request("1일차 첫번째 일정 제거해줘"),
            (1, 1),
        )

        engine, llm, _ = self._engine()
        with redirect_stdout(StringIO()):
            state = engine.create_itinerary("여행")

        removed = state.itinerary["days"][0]["stops"][0]
        with redirect_stdout(StringIO()):
            updated = engine.update_itinerary_from_chat(
                state,
                "1일차 첫번째 일정 제거해줘",
            )

        remaining_ids = {
            stop["content_id"]
            for stop in updated.itinerary["days"][0]["stops"]
        }
        self.assertEqual(len(remaining_ids), 4)
        self.assertNotIn(removed["content_id"], remaining_ids)
        self.assertNotIn(removed["content_id"], updated.used_content_ids)
        self.assertEqual(llm.revision_calls, [])

    def test_add_after_uses_current_position_after_a_delete(self) -> None:
        engine, llm, retrieval = self._engine()
        retrieval.places = (*retrieval.places, _place(6, "New cafe", "restaurants"))
        with redirect_stdout(StringIO()):
            state = engine.create_itinerary("trip")

        removed_title = state.itinerary["days"][0]["stops"][1]["title"]
        llm.delta = ConditionDelta(remove_places=(removed_title,))
        with redirect_stdout(StringIO()):
            after_delete = engine.update_itinerary_from_chat(state, "delete")

        remaining_ids = [
            slot.candidates[0].content_id for slot in after_delete.state.slots
        ]
        anchor_title = after_delete.state.itinerary["days"][0]["stops"][1]["title"]
        llm.delta = ConditionDelta(
            add_must_visit_places=("New cafe",),
            affected_slots=("food",),
            insert_after=anchor_title,
        )
        with redirect_stdout(StringIO()):
            after_add = engine.update_itinerary_from_chat(after_delete.state, "add")

        self.assertEqual(
            [slot.candidates[0].content_id for slot in after_add.state.slots],
            [*remaining_ids[:2], 6, *remaining_ids[2:]],
        )


if __name__ == "__main__":
    unittest.main()
