from __future__ import annotations

import unittest

from scripts.recommend_packages import _build_smoke_payload
from src.recommender.llm_ranker import RankDecision
from src.recommender.models import PackageCandidate, PackageItem
from src.recommender.normalization import normalize_itinerary
from src.recommender.package_service import PackageRecommendationService


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
    return PackageCandidate(
        package_id=package_id,
        title=f"패키지 {package_id}",
        summary="테스트 패키지",
        region="제주 동부권",
        duration_days=1,
        estimated_price=100_000,
        match_profile=profile or {},
        items=tuple(
            PackageItem(1, index, "tourism", content_id, f"관광지 {content_id}", 60)
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


class ReverseRanker:
    def rank(self, itinerary, candidates):
        return [
            RankDecision(row.package.package_id, "LLM 테스트 설명")
            for row in reversed(candidates)
        ]


class FailingRanker:
    def rank(self, itinerary, candidates):
        raise RuntimeError("temporary failure")


class PackageRecommendationTests(unittest.TestCase):
    def test_smoke_payload_uses_stored_tourism_items_only(self):
        candidate = package(
            "smoke",
            [101, 102, 103],
            profile={
                "party_types": ["solo"],
                "themes": ["nature"],
                "paces": ["balanced"],
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

    def test_more_exact_matches_always_rank_first_even_when_llm_reverses(self):
        repository = FakeRepository(
            [
                package("one-match", [101, 201, 202]),
                package("two-matches", [101, 102, 301]),
                package("no-match", [401, 402, 403]),
            ]
        )
        service = PackageRecommendationService(repository, ranker=ReverseRanker())
        result = service.recommend(current_payload(), top_k=3)
        self.assertEqual(
            ["two-matches", "one-match", "no-match"],
            [row["package_id"] for row in result["recommendations"]],
        )
        self.assertTrue(result["meta"]["llm_used"])

    def test_profile_breaks_tie_without_overriding_overlap(self):
        repository = FakeRepository(
            [
                package("generic", [101, 201, 202]),
                package(
                    "solo-nature",
                    [101, 301, 302],
                    profile={
                        "party_types": ["solo"],
                        "themes": ["nature"],
                        "paces": ["balanced"],
                    },
                ),
            ]
        )
        result = PackageRecommendationService(repository).recommend(current_payload())
        self.assertEqual("solo-nature", result["recommendations"][0]["package_id"])

    def test_llm_failure_falls_back_to_deterministic_result(self):
        repository = FakeRepository([package("safe", [101, 102, 201])])
        result = PackageRecommendationService(
            repository, ranker=FailingRanker()
        ).recommend(current_payload())
        self.assertFalse(result["meta"]["llm_used"])
        self.assertIn("temporary failure", result["meta"]["llm_fallback_reason"])
        self.assertEqual("safe", result["recommendations"][0]["package_id"])


if __name__ == "__main__":
    unittest.main()
