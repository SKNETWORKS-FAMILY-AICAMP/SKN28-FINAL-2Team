from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import unittest
from typing import Any, Sequence

from src.aihub.similarity import (
    AIHubPatternConfig,
    AIHubPatternService,
    AIHubSimilarityRepository,
    LocalTransport,
    Pace,
    PartyType,
    TravelCondition,
    TripProfile,
    VisitPreference,
    VISIT_TYPE_CODES,
)


@dataclass(frozen=True)
class UserScenario:
    name: str
    duration_days: int
    party_type: PartyType
    local_transport: LocalTransport
    preferences: tuple[VisitPreference, ...]
    pace: Pace
    purpose_codes: tuple[str, ...]

    def condition(self) -> TravelCondition:
        return TravelCondition(
            duration_days=self.duration_days,
            party_type=self.party_type,
            local_transport=self.local_transport,
            preferred_visit_types=self.preferences,
            companion_count=1,
            pace=self.pace,
            purpose_codes=self.purpose_codes,
            entry_point="제주공항",
        )


THIRTY_USER_SCENARIOS = (
    UserScenario("solo_daytrip_transit_nature", 1, PartyType.SOLO, LocalTransport.PUBLIC_TRANSIT, (VisitPreference.NATURE,), Pace.RELAXED, ("2",)),
    UserScenario("solo_two_days_transit_food", 2, PartyType.SOLO, LocalTransport.PUBLIC_TRANSIT, (VisitPreference.FOOD_CAFE,), Pace.BALANCED, ("7",)),
    UserScenario("solo_three_days_rental_photo", 3, PartyType.SOLO, LocalTransport.RENTAL_CAR, (VisitPreference.NATURE, VisitPreference.CULTURE), Pace.PACKED, ("22",)),
    UserScenario("solo_four_days_taxi_wellness", 4, PartyType.SOLO, LocalTransport.TAXI, (VisitPreference.NATURE, VisitPreference.FOOD_CAFE), Pace.RELAXED, ("21",)),
    UserScenario("two_friends_two_days_rental", 2, PartyType.NON_FAMILY_TWO, LocalTransport.RENTAL_CAR, (VisitPreference.NATURE, VisitPreference.FOOD_CAFE), Pace.PACKED, ("7",)),
    UserScenario("two_friends_three_days_transit", 3, PartyType.NON_FAMILY_TWO, LocalTransport.PUBLIC_TRANSIT, (VisitPreference.CULTURE, VisitPreference.MARKET_SHOPPING), Pace.BALANCED, ("6",)),
    UserScenario("two_friends_four_days_own_car", 4, PartyType.NON_FAMILY_TWO, LocalTransport.OWN_CAR, (VisitPreference.TRAIL, VisitPreference.FOOD_CAFE), Pace.RELAXED, ("5",)),
    UserScenario("two_friends_five_days_taxi", 5, PartyType.NON_FAMILY_TWO, LocalTransport.TAXI, (VisitPreference.EXPERIENCE, VisitPreference.FOOD_CAFE), Pace.BALANCED, ("11",)),
    UserScenario("nonfamily_group_three_days_rental", 3, PartyType.NON_FAMILY_GROUP, LocalTransport.RENTAL_CAR, (VisitPreference.THEME_PARK, VisitPreference.FOOD_CAFE), Pace.PACKED, ("2",)),
    UserScenario("nonfamily_group_four_days_transit", 4, PartyType.NON_FAMILY_GROUP, LocalTransport.PUBLIC_TRANSIT, (VisitPreference.MARKET_SHOPPING, VisitPreference.CULTURE), Pace.BALANCED, ("1",)),
    UserScenario("nonfamily_group_five_days_mixed", 5, PartyType.NON_FAMILY_GROUP, LocalTransport.MIXED, (VisitPreference.LEISURE, VisitPreference.NATURE), Pace.PACKED, ("5",)),
    UserScenario("family_two_two_days_own_car", 2, PartyType.FAMILY_TWO, LocalTransport.OWN_CAR, (VisitPreference.NATURE, VisitPreference.FOOD_CAFE), Pace.RELAXED, ("3",)),
    UserScenario("family_two_three_days_rental", 3, PartyType.FAMILY_TWO, LocalTransport.RENTAL_CAR, (VisitPreference.HISTORY, VisitPreference.EXPERIENCE), Pace.BALANCED, ("8",)),
    UserScenario("family_two_four_days_transit", 4, PartyType.FAMILY_TWO, LocalTransport.PUBLIC_TRANSIT, (VisitPreference.CULTURE, VisitPreference.FOOD_CAFE), Pace.RELAXED, ("2",)),
    UserScenario("family_group_three_days_rental", 3, PartyType.FAMILY_GROUP, LocalTransport.RENTAL_CAR, (VisitPreference.THEME_PARK, VisitPreference.EXPERIENCE), Pace.BALANCED, ("11",)),
    UserScenario("family_group_four_days_own_car", 4, PartyType.FAMILY_GROUP, LocalTransport.OWN_CAR, (VisitPreference.NATURE, VisitPreference.MARKET_SHOPPING), Pace.PACKED, ("1",)),
    UserScenario("family_group_five_days_mixed", 5, PartyType.FAMILY_GROUP, LocalTransport.MIXED, (VisitPreference.FESTIVAL, VisitPreference.FOOD_CAFE), Pace.RELAXED, ("9",)),
    UserScenario("children_two_days_rental_theme", 2, PartyType.WITH_CHILDREN, LocalTransport.RENTAL_CAR, (VisitPreference.THEME_PARK, VisitPreference.EXPERIENCE), Pace.RELAXED, ("2",)),
    UserScenario("children_three_days_own_car_nature", 3, PartyType.WITH_CHILDREN, LocalTransport.OWN_CAR, (VisitPreference.NATURE, VisitPreference.FOOD_CAFE), Pace.BALANCED, ("3",)),
    UserScenario("children_four_days_transit_culture", 4, PartyType.WITH_CHILDREN, LocalTransport.PUBLIC_TRANSIT, (VisitPreference.CULTURE, VisitPreference.EXPERIENCE), Pace.RELAXED, ("8",)),
    UserScenario("children_five_days_rental_leisure", 5, PartyType.WITH_CHILDREN, LocalTransport.RENTAL_CAR, (VisitPreference.LEISURE, VisitPreference.THEME_PARK), Pace.PACKED, ("5",)),
    UserScenario("parents_two_days_taxi_nature", 2, PartyType.WITH_PARENTS, LocalTransport.TAXI, (VisitPreference.NATURE, VisitPreference.FOOD_CAFE), Pace.RELAXED, ("2",)),
    UserScenario("parents_three_days_rental_history", 3, PartyType.WITH_PARENTS, LocalTransport.RENTAL_CAR, (VisitPreference.HISTORY, VisitPreference.CULTURE), Pace.RELAXED, ("8",)),
    UserScenario("parents_four_days_own_car_wellness", 4, PartyType.WITH_PARENTS, LocalTransport.OWN_CAR, (VisitPreference.NATURE, VisitPreference.TRAIL), Pace.BALANCED, ("21",)),
    UserScenario("three_generations_three_days_rental", 3, PartyType.THREE_GENERATIONS, LocalTransport.RENTAL_CAR, (VisitPreference.THEME_PARK, VisitPreference.FOOD_CAFE), Pace.RELAXED, ("3",)),
    UserScenario("three_generations_four_days_own_car", 4, PartyType.THREE_GENERATIONS, LocalTransport.OWN_CAR, (VisitPreference.NATURE, VisitPreference.EXPERIENCE), Pace.RELAXED, ("7",)),
    UserScenario("three_generations_five_days_mixed", 5, PartyType.THREE_GENERATIONS, LocalTransport.MIXED, (VisitPreference.HISTORY, VisitPreference.MARKET_SHOPPING), Pace.BALANCED, ("8",)),
    UserScenario("two_friends_six_days_rental_trail", 6, PartyType.NON_FAMILY_TWO, LocalTransport.RENTAL_CAR, (VisitPreference.TRAIL, VisitPreference.NATURE), Pace.PACKED, ("28",)),
    UserScenario("solo_seven_days_transit_discovery", 7, PartyType.SOLO, LocalTransport.PUBLIC_TRANSIT, (VisitPreference.CULTURE, VisitPreference.EXPERIENCE), Pace.BALANCED, ("24",)),
    UserScenario("family_group_six_days_rental_festival", 6, PartyType.FAMILY_GROUP, LocalTransport.RENTAL_CAR, (VisitPreference.FESTIVAL, VisitPreference.FOOD_CAFE), Pace.BALANCED, ("9",)),
)


class FakePatternRepository:
    def __init__(
        self,
        profiles: Sequence[TripProfile],
        routes: Sequence[dict[str, Any]],
    ) -> None:
        self.profiles = list(profiles)
        self.routes = list(routes)

    def fetch_trip_profiles(self, *, min_usable_visits: int) -> list[TripProfile]:
        return [
            profile
            for profile in self.profiles
            if profile.usable_visit_count >= min_usable_visits
        ]

    def fetch_trip_routes(
        self,
        travel_ids: Sequence[str],
    ) -> list[dict[str, Any]]:
        selected = set(travel_ids)
        return [
            route for route in self.routes if route["travel_id"] in selected
        ]


class ThirtyUserScenarioTests(unittest.TestCase):
    def assert_scenario(self, index: int, scenario: UserScenario) -> None:
        condition = scenario.condition()
        expected_duration = 2 if condition.duration_days == 1 else condition.duration_days
        expected = _matching_profile(
            condition,
            travel_id=f"matching-{index:02d}",
            duration_days=expected_duration,
        )
        distractor = _distractor_profile(
            condition,
            travel_id=f"distractor-{index:02d}",
        )
        routes = [
            _route_row(expected.travel_id, condition.preferred_visit_types[0]),
            _route_row(distractor.travel_id, VisitPreference.MARKET_SHOPPING),
        ]
        service = AIHubPatternService(
            FakePatternRepository([distractor, expected], routes),
            AIHubPatternConfig(top_k=1),
        )

        context = service.build_llm_context(condition)

        self.assertEqual(
            context["reference_trip_patterns"][0]["reference_trip_id"],
            _reference_key(expected.travel_id),
        )
        self.assertGreaterEqual(
            context["reference_trip_patterns"][0]["match_score"],
            80,
        )
        self.assertEqual(
            context["user_constraints"]["preferred_visit_types"],
            [item.value for item in condition.preferred_visit_types],
        )
        self.assertEqual(
            context["context_policy"]["place_source"],
            "tourapi_vector_candidates_only",
        )
        self.assertEqual(
            context["context_policy"]["aihub_tourapi_mapping"],
            "ignored",
        )
        first_day = context["reference_trip_patterns"][0]["days"][0]
        self.assertIsNotNone(first_day["region"])
        self.assertGreater(first_day["slot_count"], 0)
        self.assertIn("target_collections", first_day["slots"][0])
        serialized = json.dumps(context, ensure_ascii=False)
        self.assertNotIn(expected.travel_id, serialized)
        self.assertNotIn(
            f"{condition.preferred_visit_types[0].value} place",
            serialized,
        )
        self.assertNotIn("테스트로 1", serialized)
        for private_field in (
            "traveler_id",
            "income",
            "job_nm",
            "residence_sgg_cd",
            "marr_stts",
        ):
            self.assertNotIn(private_field, serialized)


class TravelConditionTests(unittest.TestCase):
    def test_requires_the_four_minimum_matching_conditions(self) -> None:
        required_fields = {
            "duration_days": 3,
            "party_type": "non_family_two",
            "local_transport": "rental_car",
            "preferred_visit_types": ["nature", "food_cafe"],
        }

        condition = TravelCondition.from_mapping(required_fields)

        self.assertEqual(condition.duration_days, 3)
        self.assertEqual(condition.party_type, PartyType.NON_FAMILY_TWO)
        self.assertEqual(condition.local_transport, LocalTransport.RENTAL_CAR)
        self.assertEqual(len(condition.preferred_visit_types), 2)

    def test_rejects_blank_preferences(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "at least one preferred_visit_type",
        ):
            TravelCondition(
                duration_days=3,
                party_type=PartyType.SOLO,
                local_transport=LocalTransport.PUBLIC_TRANSIT,
                preferred_visit_types=(),
                companion_count=1,
            )


class RepositoryQueryTests(unittest.TestCase):
    def test_route_query_uses_parameters_and_closes_resources(self) -> None:
        cursor = RecordingCursor([])
        connection = RecordingConnection(cursor)
        repository = AIHubSimilarityRepository(
            connection_factory=lambda: connection
        )

        rows = repository.fetch_trip_routes(["trip-1", "trip-2", "trip-1"])

        self.assertEqual(rows, [])
        self.assertIn("IN (%s, %s)", cursor.sql)
        self.assertNotIn("aihub_places", cursor.sql)
        self.assertNotIn("tourapi_content_id", cursor.sql)
        self.assertIn("visit_area_nm AS place_name", cursor.sql)
        self.assertIn("road_nm_addr AS road_address", cursor.sql)
        self.assertIn("lotno_addr AS lot_address", cursor.sql)
        self.assertEqual(cursor.params, ("trip-1", "trip-2"))
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)


class RecordingCursor:
    def __init__(self, rows: Sequence[dict[str, Any]]) -> None:
        self.rows = list(rows)
        self.sql = ""
        self.params: Any = None
        self.closed = False

    def execute(self, sql: str, params: Any = None) -> None:
        self.sql = sql
        self.params = params

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows

    def close(self) -> None:
        self.closed = True


class RecordingConnection:
    def __init__(self, cursor: RecordingCursor) -> None:
        self._cursor = cursor
        self.closed = False

    def cursor(self, *, dictionary: bool = False) -> RecordingCursor:
        if not dictionary:
            raise AssertionError("repository must request dictionary rows")
        return self._cursor

    def close(self) -> None:
        self.closed = True


def _matching_profile(
    condition: TravelCondition,
    *,
    travel_id: str,
    duration_days: int,
) -> TripProfile:
    if condition.pace == Pace.RELAXED:
        stops_per_day, stay_minutes = 4, 90.0
    elif condition.pace == Pace.PACKED:
        stops_per_day, stay_minutes = 7, 45.0
    else:
        stops_per_day, stay_minutes = 5, 60.0
    counts = {preference: 0 for preference in VisitPreference}
    for preference in condition.preferred_visit_types:
        counts[preference] = max(duration_days, 1)
    return TripProfile(
        travel_id=travel_id,
        duration_days=duration_days,
        party_type=condition.party_type,
        local_transport=condition.local_transport,
        companion_count=condition.companion_count or 0,
        purpose_codes=frozenset(condition.purpose_codes),
        visit_type_counts=counts,
        usable_visit_count=max(stops_per_day * duration_days, 3),
        average_stay_minutes=stay_minutes,
        average_satisfaction=4.8,
    )


def _distractor_profile(
    condition: TravelCondition,
    *,
    travel_id: str,
) -> TripProfile:
    party_type = (
        PartyType.FAMILY_GROUP
        if condition.party_type == PartyType.SOLO
        else PartyType.SOLO
    )
    transport = (
        LocalTransport.PUBLIC_TRANSIT
        if condition.local_transport
        in {LocalTransport.RENTAL_CAR, LocalTransport.OWN_CAR}
        else LocalTransport.RENTAL_CAR
    )
    unrelated_preference = next(
        item
        for item in VisitPreference
        if item not in condition.preferred_visit_types
    )
    counts = {preference: 0 for preference in VisitPreference}
    counts[unrelated_preference] = 10
    return TripProfile(
        travel_id=travel_id,
        duration_days=min(condition.duration_days + 4, 9),
        party_type=party_type,
        local_transport=transport,
        companion_count=0,
        purpose_codes=frozenset({"99"}),
        visit_type_counts=counts,
        usable_visit_count=10,
        average_stay_minutes=20,
        average_satisfaction=3,
    )


def _route_row(
    travel_id: str,
    preference: VisitPreference,
) -> dict[str, Any]:
    return {
        "travel_id": travel_id,
        "day_no": 1,
        "visit_area_id": f"{travel_id}-visit",
        "visit_order": 1,
        "place_name": f"{preference.value} place",
        "road_address": "제주특별자치도 제주시 테스트로 1",
        "lot_address": None,
        "longitude": 126.5,
        "latitude": 33.5,
        "visit_area_type_cd": VISIT_TYPE_CODES[preference][0],
        "stay_minutes": 60,
        "satisfaction": 5,
        "recommendation_score": 5,
        "activity_type_codes": "4",
    }


def _scenario_test(index: int, scenario: UserScenario):
    def test(self: ThirtyUserScenarioTests) -> None:
        self.assert_scenario(index, scenario)

    test.__name__ = f"test_{index:02d}_{scenario.name}"
    return test


def _reference_key(travel_id: str) -> str:
    digest = hashlib.sha256(travel_id.encode("utf-8")).hexdigest()[:16]
    return f"aihub-trip:{digest}"


for scenario_index, user_scenario in enumerate(THIRTY_USER_SCENARIOS, start=1):
    setattr(
        ThirtyUserScenarioTests,
        f"test_{scenario_index:02d}_{user_scenario.name}",
        _scenario_test(scenario_index, user_scenario),
    )


if __name__ == "__main__":
    unittest.main()
