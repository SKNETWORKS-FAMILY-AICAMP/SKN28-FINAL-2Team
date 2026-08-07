from __future__ import annotations

from dataclasses import replace
import unittest

from scripts.recommend_packages import _build_smoke_payload
from src.models import (
    ItineraryState,
    LocalTransport,
    Pace,
    PartyType,
    TravelCondition,
    VisitPreference,
)
from src.recommender.models import PackageCandidate, PackageItem
from src.recommender.normalization import normalize_itinerary
from src.recommender.package_service import PackageRecommendationService
from src.recommender.profile_mapping import (
    build_package_profile,
    categories_from_tags,
)
from src.recommender.package_repository import _group_packages


def current_payload() -> dict:
    return {
        "condition": {
            "duration_days": 1,
            "party_type": "solo",
            "preferred_visit_types": ["nature"],
            "pace": "balanced",
        },
        "itinerary": {
            "days": [
                {
                    "day": 1,
                    "stops": [
                        {"sequence": 1, "role": "visit", "content_id": 101, "title": "A"},
                        {"sequence": 2, "role": "meal", "content_id": 900, "title": "식당"},
                        {"sequence": 3, "role": "visit", "content_id": 102, "title": "B"},
                        {"sequence": 4, "role": "visit", "content_id": 103, "title": "C"},
                    ],
                }
            ]
        },
    }


def package(package_id: str, place_ids: list[int], *, profile: dict | None = None):
    profile = profile or {}
    return PackageCandidate(
        package_id=package_id,
        title=f"패키지 {package_id}",
        summary="테스트 패키지",
        region="제주 동부권",
        duration_days=1,
        estimated_price=100_000,
        companion_types=tuple(profile.get("companion_types", [])),
        place_categories=tuple(profile.get("place_categories", [])),
        items=tuple(
            PackageItem(
                1,
                index,
                "tourism",
                content_id,
                f"관광지 {content_id}",
                60,
                126.5,
                33.4,
            )
            for index, content_id in enumerate(place_ids, start=1)
        ),
    )


class FakeRepository:
    def __init__(self, packages):
        self.packages = packages

    def find_active_by_duration(self, duration_days):
        return [row for row in self.packages if row.duration_days == duration_days]

    def get_places(self, content_ids):
        return {
            content_id: {
                "content_id": content_id,
                "title": f"관광지 {content_id}",
                "longitude": 126.5,
                "latitude": 33.4,
            }
            for content_id in content_ids
        }


class PackageRecommendationTests(unittest.TestCase):
    def test_grouped_packages_keep_their_own_database_ids(self):
        common = {
            "summary": "",
            "region": "제주",
            "duration_days": 1,
            "estimated_price": 100000,
            "companion": "solo",
            "tags": "nature",
            "item_id": None,
        }
        rows = [
            {**common, "package_db_id": 101, "package_id": "PKG-101", "title": "첫 패키지"},
            {**common, "package_db_id": 202, "package_id": "PKG-202", "title": "둘째 패키지"},
        ]

        candidates = _group_packages(rows)

        self.assertEqual(
            [(row.package_id, row.database_id) for row in candidates],
            [("PKG-101", 101), ("PKG-202", 202)],
        )

    def test_latest_rag_engine_state_is_supported(self):
        state = ItineraryState(
            condition=TravelCondition(
                duration_days=1,
                party_type=PartyType.SOLO,
                local_transport=LocalTransport.RENTAL_CAR,
                preferred_visit_types=(VisitPreference.NATURE,),
                pace=Pace.BALANCED,
            ),
            slots=[],
            itinerary=current_payload()["itinerary"],
            used_content_ids={101, 102, 103},
        )

        normalized = normalize_itinerary(state.to_dict())

        self.assertEqual(PartyType.SOLO.value, normalized.conditions["party_type"])
        self.assertEqual(
            [101, 102, 103],
            [row.content_id for row in normalized.tourism_stops],
        )

    def test_smoke_payload_uses_stored_tourism_items_only(self):
        candidate = package(
            "smoke",
            [101, 102, 103],
            profile={
                "companion_types": ["solo"],
                "place_categories": ["nature"],
                "category_counts": {"nature": 3},
            },
        )
        payload = _build_smoke_payload(candidate)
        stops = payload["itinerary"]["days"][0]["stops"]
        self.assertEqual([101, 102, 103], [row["content_id"] for row in stops])
        self.assertEqual("solo", payload["condition"]["party_type"])

    def test_current_rag_schema_excludes_meals(self):
        normalized = normalize_itinerary(current_payload())
        self.assertEqual([101, 102, 103], [row.content_id for row in normalized.tourism_stops])

    def test_legacy_flat_schema_is_supported(self):
        normalized = normalize_itinerary(
            {
                "conditions": {"duration_days": 1},
                "itinerary": [
                    {"day": 1, "sequence": 1, "content_id": 101, "slot_kind": "tourism"},
                    {"day": 1, "sequence": 2, "content_id": 900, "slot_kind": "meal"},
                ],
            }
        )
        self.assertEqual([101], [row.content_id for row in normalized.tourism_stops])

    def test_more_exact_matches_always_rank_first(self):
        repository = FakeRepository(
            [
                package("one-match", [101, 201, 202]),
                package("two-matches", [101, 102, 301]),
                package("no-match", [401, 402, 403]),
            ]
        )
        service = PackageRecommendationService(repository)
        result = service.recommend(current_payload(), top_k=3)
        self.assertEqual(
            ["two-matches", "one-match", "no-match"],
            [row["package_id"] for row in result["recommendations"]],
        )

    def test_profile_breaks_tie_without_overriding_overlap(self):
        repository = FakeRepository(
            [
                package("generic", [101, 201, 202]),
                package(
                    "solo-nature",
                    [101, 301, 302],
                    profile={
                        "companion_types": ["solo"],
                        "place_categories": ["nature"],
                        "category_counts": {"nature": 3},
                    },
                ),
            ]
        )
        result = PackageRecommendationService(repository).recommend(current_payload())
        self.assertEqual("solo-nature", result["recommendations"][0]["package_id"])

    def test_requested_score_weights_are_exposed(self):
        candidate = package(
            "perfect",
            [101, 102, 103],
            profile={
                "companion_types": ["solo"],
                "place_categories": ["nature"],
                "category_counts": {"nature": 3},
            },
        )
        result = PackageRecommendationService(FakeRepository([candidate])).recommend(
            current_payload()
        )
        recommendation = result["recommendations"][0]

        self.assertEqual(50.0, recommendation["score"]["tourism_match"])
        self.assertEqual(40.0, recommendation["score"]["user_conditions"])
        self.assertEqual(10.0, recommendation["score"]["region_and_route"])
        self.assertEqual(100.0, recommendation["score"]["total"])
        self.assertEqual(
            {
                "tourism_match": 50,
                "user_conditions": {
                        "total": 40,
                        "companion": 20,
                        "place_category": 15,
                        "season": 5,
                },
                "region_and_route": 10,
            },
            result["meta"]["score_weights"],
        )

    def test_user_conditions_can_outweigh_a_weak_place_overlap(self):
        repository = FakeRepository(
            [
                package("one-match-generic", [101, 201, 202]),
                package(
                    "condition-match",
                    [301, 302, 303],
                    profile={
                        "companion_types": ["solo"],
                        "place_categories": ["nature"],
                        "category_counts": {"nature": 3},
                    },
                ),
            ]
        )

        result = PackageRecommendationService(repository).recommend(current_payload())

        self.assertEqual(
            "condition-match", result["recommendations"][0]["package_id"]
        )
        evidence = result["recommendations"][0]["evidence"]
        self.assertEqual(20.0, evidence["companion_score"])
        self.assertEqual(15.0, evidence["category_score"])
        self.assertEqual(5.0, evidence["season_score"])

    def test_old_itinerary_values_are_normalized_to_new_profile_values(self):
        candidate = package(
            "legacy-condition-compatible",
            [101, 102, 103],
            profile={
                "companion_types": ["friend", "couple"],
                "place_categories": ["food", "cafe", "activity", "shopping"],
                "category_counts": {
                    "food": 1,
                    "cafe": 1,
                    "activity": 1,
                    "shopping": 1,
                },
            },
        )
        payload = current_payload()
        payload["condition"]["party_type"] = "non_family_two"
        payload["condition"]["preferred_visit_types"] = [
            "food_cafe",
            "leisure",
            "market_shopping",
        ]

        recommendation = PackageRecommendationService(
            FakeRepository([candidate])
        ).recommend(payload)["recommendations"][0]

        self.assertEqual(20.0, recommendation["evidence"]["companion_score"])
        self.assertEqual(15.0, recommendation["evidence"]["category_score"])

    def test_start_date_matches_season_in_package_title(self):
        payload = current_payload()
        payload["condition"]["start_date"] = "2026-01-15"
        summer = replace(
            package(
                "summer",
                [101, 102, 103],
                profile={
                    "companion_types": ["solo"],
                    "place_categories": ["nature"],
                },
            ),
            title="제주 여름 여행",
        )
        winter = replace(
            package(
                "winter",
                [101, 102, 103],
                profile={
                    "companion_types": ["solo"],
                    "place_categories": ["nature"],
                },
            ),
            title="제주 겨울 여행",
        )

        recommendations = PackageRecommendationService(
            FakeRepository([summer, winter])
        ).recommend(payload, top_k=2)["recommendations"]

        self.assertEqual(
            ["winter", "summer"],
            [row["package_id"] for row in recommendations],
        )
        self.assertEqual(5.0, recommendations[0]["evidence"]["season_score"])
        self.assertTrue(recommendations[0]["evidence"]["season_match"])
        self.assertEqual(0.0, recommendations[1]["evidence"]["season_score"])
        self.assertFalse(recommendations[1]["evidence"]["season_match"])

    def test_package_profile_is_derived_from_tags_and_old_keys_are_removed(self):
        profile = build_package_profile(
            {
                "party_types": ["non_family_two", "family_two"],
                "themes": ["festival"],
                "paces": ["relaxed"],
            },
            [
                ["자연관광", "place_subtype:attraction"],
                ["체험관광", "place_subtype:land_leisure"],
                ["음식", "place_subtype:restaurant"],
            ],
        )

        self.assertEqual(
            ["friend", "couple", "family"], profile["companion_types"]
        )
        self.assertEqual(
            ["nature", "experience", "food", "activity"],
            profile["place_categories"],
        )
        self.assertNotIn("themes", profile)
        self.assertNotIn("paces", profile)
        self.assertEqual(
            ("festival", "shopping"),
            categories_from_tags(
                ["지역축제공연행사", "place_subtype:local_specialty"]
            ),
        )

if __name__ == "__main__":
    unittest.main()
