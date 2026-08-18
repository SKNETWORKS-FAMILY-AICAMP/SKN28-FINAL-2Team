from __future__ import annotations

import unittest

from src.recommender.models import PackageCandidate, PackageItem
from src.recommender.normalization import normalize_itinerary
from src.recommender.package_service import PackageRecommendationService
from src.recommender.package_profile import (
    build_match_profile,
    infer_package_style,
    infer_package_style_from_profile,
)
from src.recommender.package_repository import _deserialize_match_profile, _PACKAGE_SELECT
from src.recommender.scoring import deterministic_sort_key, score_package


def _payload() -> dict:
    return {
        "condition": {
            "duration_days": 1,
            "party_type": "solo",
            "pace": "relaxed",
            "preferred_visit_types": ["nature"],
        },
        "itinerary": {
            "days": [
                {
                    "day": 1,
                    "stops": [
                        {"sequence": 2, "role": "visit", "content_id": 2, "title": "오름"},
                        {"sequence": 1, "role": "visit", "content_id": 1, "title": "해변"},
                        {"sequence": 3, "role": "food", "content_id": 99, "title": "식당"},
                    ],
                }
            ]
        },
    }


def _package(package_id="PKG-1", *, duration=1, matching=True) -> PackageCandidate:
    ids = (1, 2) if matching else (10, 20)
    return PackageCandidate(
        package_id=package_id,
        title="제주 패키지",
        summary="요약",
        region="제주",
        duration_days=duration,
        estimated_price=100000,
        companion_types=("solo",),
        place_categories=("nature",),
        thumbnail_url="image.jpg",
        match_profile={
            "party_types": ["solo"],
            "themes": ["nature"],
            "paces": ["relaxed"],
        },
        items=(
            PackageItem(
                day=1,
                sequence=1,
                item_type="tourism",
                content_id=ids[0],
                title="해변",
                stay_minutes=60,
                longitude=126.5,
                latitude=33.5,
            ),
            PackageItem(
                day=1,
                sequence=2,
                item_type="tourism",
                content_id=ids[1],
                title="오름",
                stay_minutes=60,
                longitude=126.6,
                latitude=33.6,
            ),
            PackageItem(
                day=None,
                sequence=None,
                item_type="hotel",
                content_id=30,
                title="호텔",
            ),
        ),
    )


class FakePackageRepository:
    def __init__(self, packages) -> None:
        self.packages = list(packages)
        self.requested_ids = []

    def get_places(self, content_ids):
        self.requested_ids.append(list(content_ids))
        return {
            1: {"title": "해변", "longitude": 126.5, "latitude": 33.5},
            2: {"title": "오름", "longitude": 126.6, "latitude": 33.6},
        }

    def find_active_by_duration(self, duration_days):
        return [package for package in self.packages if package.duration_days == duration_days]


class NormalizationTests(unittest.TestCase):
    def test_normalizes_nested_response_sorts_and_ignores_non_tourism_roles(self) -> None:
        itinerary = normalize_itinerary(_payload())
        self.assertEqual([stop.content_id for stop in itinerary.tourism_stops], [1, 2])

    def test_normalizes_legacy_flat_response(self) -> None:
        itinerary = normalize_itinerary(
            {
                "conditions": {"duration_days": 1},
                "itinerary": [
                    {"day": 1, "slot_kind": "tourism", "content_id": 3},
                    {"day": 1, "slot_kind": "hotel", "content_id": 4},
                ],
            }
        )
        self.assertEqual([stop.content_id for stop in itinerary.tourism_stops], [3])

    def test_rejects_invalid_duration_and_missing_tourism_stops(self) -> None:
        payload = _payload()
        payload["condition"]["duration_days"] = 6
        with self.assertRaisesRegex(ValueError, "between 1 and 5"):
            normalize_itinerary(payload)

        with self.assertRaisesRegex(ValueError, "no tourism stops"):
            normalize_itinerary(
                {
                    "condition": {"duration_days": 1},
                    "itinerary": {"days": [{"day": 1, "stops": []}]},
                }
            )


class PackageProfileTests(unittest.TestCase):
    def test_builds_legacy_profile_from_companion_and_tags(self) -> None:
        profile = build_match_profile(
            "solo,friend,couple,family",
            "nature,culture,experience",
        )
        self.assertEqual(
            profile["party_types"],
            [
                "family_group",
                "family_two",
                "non_family_group",
                "non_family_two",
                "solo",
                "three_generations",
                "with_children",
                "with_parents",
            ],
        )
        self.assertEqual(profile["themes"], ["nature", "culture", "experience"])

    def test_infers_frontend_style_from_new_columns(self) -> None:
        self.assertEqual(infer_package_style("family", "experience"), "family")
        self.assertEqual(infer_package_style("friend", "experience"), "activity")
        self.assertEqual(infer_package_style("solo", "nature"), "healing")

    def test_uses_stored_match_profile_for_frontend_style(self) -> None:
        self.assertEqual(
            infer_package_style_from_profile(
                {"party_types": ["with_children"], "themes": ["nature"]}
            ),
            "family",
        )
        self.assertEqual(
            infer_package_style_from_profile(
                {"party_types": ["solo"], "themes": ["experience"]}
            ),
            "activity",
        )

    def test_deserializes_mysql_json_match_profile(self) -> None:
        profile = _deserialize_match_profile(
            '{"party_types":["solo"],"themes":["nature"],"paces":[]}'
        )
        self.assertEqual(profile["party_types"], ["solo"])
        with self.assertRaisesRegex(ValueError, "must be a JSON object"):
            _deserialize_match_profile([])

    def test_repository_select_uses_fix_backend_profile_columns(self) -> None:
        self.assertNotIn("tp.match_profile", _PACKAGE_SELECT)
        self.assertIn("tp.companion", _PACKAGE_SELECT)
        self.assertIn("tp.tags AS package_tags", _PACKAGE_SELECT)


class PackageScoringTests(unittest.TestCase):
    def test_perfect_match_reaches_full_weighted_score(self) -> None:
        itinerary = normalize_itinerary(_payload())
        itinerary = type(itinerary)(
            itinerary.duration_days,
            itinerary.conditions,
            tuple(
                type(stop)(
                    stop.day,
                    stop.sequence,
                    stop.content_id,
                    stop.title,
                    126.5 if stop.content_id == 1 else 126.6,
                    33.5 if stop.content_id == 1 else 33.6,
                )
                for stop in itinerary.tourism_stops
            ),
        )

        scored = score_package(itinerary, _package())

        self.assertEqual(scored.score.exact_overlap, 50.0)
        self.assertEqual(scored.score.route_fit, 6.0)
        self.assertEqual(scored.score.profile_fit, 40.0)
        self.assertEqual(scored.score.nearby_fit, 4.0)
        self.assertEqual(scored.score.total, 100.0)

    def test_duration_mismatch_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "duration must match"):
            score_package(normalize_itinerary(_payload()), _package(duration=2))

    def test_deterministic_sort_uses_package_id_after_ties(self) -> None:
        itinerary = normalize_itinerary(_payload())
        scored = [score_package(itinerary, _package("PKG-B")), score_package(itinerary, _package("PKG-A"))]
        ordered = sorted(scored, key=deterministic_sort_key)
        self.assertEqual([row.package.package_id for row in ordered], ["PKG-A", "PKG-B"])


class PackageRecommendationServiceTests(unittest.TestCase):
    def test_recommend_returns_ranked_serialized_packages(self) -> None:
        repository = FakePackageRepository([_package("PKG-B"), _package("PKG-A")])
        result = PackageRecommendationService(repository).recommend(_payload(), top_k=1)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["recommendations"][0]["package_id"], "PKG-A")
        self.assertEqual(result["recommendations"][0]["rank"], 1)
        self.assertEqual(repository.requested_ids, [[1, 2]])

    def test_no_candidates_has_explicit_status(self) -> None:
        result = PackageRecommendationService(FakePackageRepository([])).recommend(_payload())
        self.assertEqual(result["status"], "no_candidates")
        self.assertEqual(result["recommendations"], [])

    def test_rejects_nonpositive_top_k_and_shortlist_size(self) -> None:
        with self.assertRaisesRegex(ValueError, "shortlist_size"):
            PackageRecommendationService(FakePackageRepository([]), shortlist_size=0)
        with self.assertRaisesRegex(ValueError, "top_k"):
            PackageRecommendationService(FakePackageRepository([])).recommend(_payload(), top_k=0)


if __name__ == "__main__":
    unittest.main()
