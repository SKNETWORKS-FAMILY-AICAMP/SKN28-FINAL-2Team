from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.preprocessing.map_aihub_places import load_tour_candidates
from src.aihub.place_mapping import (
    GroupedAIHubPlace,
    TourPlaceCandidate,
    TourPlaceMatcher,
    VisitPlaceRecord,
    group_aihub_visits,
    normalize_address,
    normalize_name,
)


from src.common.paths import AIHUB_DATABASE_ROOT


def visit(
    visit_id: str,
    name: str,
    *,
    poi_id: str | None = None,
    address: str | None = None,
    longitude: float | None = 126.239,
    latitude: float | None = 33.394,
) -> VisitPlaceRecord:
    return VisitPlaceRecord(
        travel_id="travel-1",
        visit_area_id=visit_id,
        name=name,
        poi_name=None,
        road_address=address,
        lot_address=None,
        longitude=longitude,
        latitude=latitude,
        poi_id=poi_id,
        visit_area_type_cd="1",
    )


def grouped_place(
    name: str,
    *,
    address: str | None = None,
    longitude: float | None = 126.239,
    latitude: float | None = 33.394,
) -> GroupedAIHubPlace:
    return GroupedAIHubPlace(
        aihub_place_id=1,
        canonical_name=name,
        normalized_name=normalize_name(name),
        aliases=(),
        poi_ids=(),
        road_address=address,
        lot_address=None,
        longitude=longitude,
        latitude=latitude,
        visit_area_type_cd="1",
        visit_count=1,
        identity_method="UNIQUE_VISIT",
        member_keys=(("travel-1", "visit-1"),),
    )


class AIHubPlaceMappingTests(unittest.TestCase):
    def test_load_tour_candidates_accepts_consistent_version(self) -> None:
        payload = {
            "preprocessing_version": "places-v4",
            "documents": [
                {
                    "metadata": {
                        "contentid": 101,
                        "title": "테스트 장소",
                        "aliases": [],
                        "address": "제주특별자치도 제주시",
                        "longitude": 126.5,
                        "latitude": 33.5,
                        "preprocessing_version": "places-v4",
                    }
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tourapi.json"
            path.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )

            candidates = load_tour_candidates(path, {101})

        self.assertEqual([candidate.content_id for candidate in candidates], [101])

    def test_load_tour_candidates_rejects_inconsistent_versions(self) -> None:
        payload = {
            "preprocessing_version": "places-v4",
            "documents": [
                {
                    "metadata": {
                        "contentid": 101,
                        "title": "테스트 장소",
                        "preprocessing_version": "places-v3",
                    }
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tourapi.json"
            path.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "inconsistent"):
                load_tour_candidates(path, {101})

    def test_normalization_handles_spacing_and_address_parentheses(self) -> None:
        self.assertEqual(normalize_name("오설록 티 뮤지엄"), "오설록티뮤지엄")
        self.assertEqual(
            normalize_address("제주특별자치도 제주시 관덕로 15 (일도일동)"),
            normalize_address("제주시 관덕로 15"),
        )

    def test_same_poi_and_nearby_coordinates_are_grouped(self) -> None:
        places, memberships = group_aihub_visits(
            [
                visit("v1", "호텔", poi_id="POI-1"),
                visit("v2", "호텔 레스토랑", poi_id="POI-1", longitude=126.2392),
            ]
        )
        self.assertEqual(len(places), 1)
        self.assertEqual(memberships[("travel-1", "v1")], memberships[("travel-1", "v2")])

    def test_reused_poi_far_away_does_not_merge_branches(self) -> None:
        places, _ = group_aihub_visits(
            [
                visit("v1", "카페 함덕점", poi_id="POI-1", address="제주시 조천읍"),
                visit("v2", "카페 협재점", poi_id="POI-1", address="제주시 한림읍", longitude=126.25),
            ]
        )
        self.assertEqual(len(places), 2)

    def test_reused_poi_and_broad_same_address_do_not_merge_distant_places(self) -> None:
        places, _ = group_aihub_visits(
            [
                visit(
                    "v1",
                    "답다니 탑망대",
                    poi_id="POI-REUSED",
                    address="제주특별자치도 제주시 우도면 연평리",
                    longitude=126.951886,
                    latitude=33.5247371,
                ),
                visit(
                    "v2",
                    "우도해양도립공원",
                    poi_id="POI-REUSED",
                    address="제주특별자치도 제주시 우도면 연평리",
                    longitude=126.9552577,
                    latitude=33.4826407,
                ),
            ]
        )
        self.assertEqual(len(places), 2)

    def test_same_name_and_address_are_grouped_without_poi(self) -> None:
        places, _ = group_aihub_visits(
            [
                visit("v1", "협재 해수욕장", address="제주시 한림읍 한림로 329-10", longitude=None, latitude=None),
                visit("v2", "협재해수욕장", address="제주특별자치도 제주시 한림읍 한림로 329-10", longitude=None, latitude=None),
            ]
        )
        self.assertEqual(len(places), 1)

    def test_same_name_and_nearby_coordinates_are_grouped(self) -> None:
        places, _ = group_aihub_visits(
            [
                visit("v1", "협재해수욕장"),
                visit("v2", "협재 해수욕장", longitude=126.2393),
            ]
        )
        self.assertEqual(len(places), 1)

    def test_same_name_far_away_is_not_grouped(self) -> None:
        places, _ = group_aihub_visits(
            [
                visit("v1", "중앙식당", address="제주시", longitude=126.2),
                visit("v2", "중앙식당", address="서귀포시", longitude=126.8),
            ]
        )
        self.assertEqual(len(places), 2)

    def test_exact_name_and_address_is_automatically_matched(self) -> None:
        candidate = TourPlaceCandidate(
            content_id=127490,
            title="협재해수욕장",
            aliases=(),
            address="제주특별자치도 제주시 한림읍 한림로 329-10",
            longitude=126.239,
            latitude=33.394,
        )
        result = TourPlaceMatcher([candidate]).match(
            grouped_place(
                "협재 해수욕장",
                address="제주시 한림읍 한림로 329-10",
            )
        )
        self.assertEqual(result.status, "MATCHED")
        self.assertEqual(result.tourapi_content_id, 127490)

    def test_name_only_match_requires_review(self) -> None:
        candidate = TourPlaceCandidate(
            content_id=1,
            title="중앙식당",
            aliases=(),
            address=None,
            longitude=None,
            latitude=None,
        )
        result = TourPlaceMatcher([candidate]).match(
            grouped_place("중앙식당", longitude=None, latitude=None)
        )
        self.assertEqual(result.status, "REVIEW")

    def test_bracketed_tourapi_title_matches_plain_aihub_name(self) -> None:
        candidate = TourPlaceCandidate(
            content_id=126435,
            title="성산일출봉 [유네스코 세계자연유산]",
            aliases=(),
            address="제주특별자치도 서귀포시 성산읍 일출로 284-12",
            longitude=126.9415156,
            latitude=33.4581111,
        )
        result = TourPlaceMatcher([candidate]).match(
            grouped_place(
                "성산일출봉",
                longitude=126.9405375,
                latitude=33.459135,
            )
        )
        self.assertEqual(result.status, "MATCHED")
        self.assertEqual(result.tourapi_content_id, 126435)

    def test_exact_name_with_conflicting_coordinates_requires_review(self) -> None:
        candidate = TourPlaceCandidate(
            content_id=129400,
            title="김녕해수욕장",
            aliases=(),
            address="제주특별자치도 제주시 구좌읍 구좌해안로 237",
            longitude=126.7365512,
            latitude=33.5572081,
        )
        result = TourPlaceMatcher([candidate]).match(
            grouped_place(
                "김녕해수욕장",
                longitude=126.759314,
                latitude=33.5574389,
            )
        )
        self.assertEqual(result.status, "REVIEW")
        self.assertEqual(result.tourapi_content_id, 129400)

    def test_fuzzy_same_address_match_requires_review(self) -> None:
        candidate = TourPlaceCandidate(
            content_id=1,
            title="CU 제주항국제여객터미널",
            aliases=(),
            address="제주특별자치도 제주시 임항로 191",
            longitude=126.543,
            latitude=33.518,
        )
        result = TourPlaceMatcher([candidate]).match(
            grouped_place(
                "제주항 국제여객터미널",
                address="제주특별자치도 제주시 임항로 191",
                longitude=126.5432,
                latitude=33.5182,
            )
        )
        self.assertEqual(result.status, "REVIEW")

    def test_schema_does_not_drop_source_tables(self) -> None:
        schema = (AIHUB_DATABASE_ROOT / "sql" / "aihub_place_mapping.sql").read_text(
            encoding="utf-8"
        ).lower()
        self.assertIn("create table if not exists aihub_places", schema)
        self.assertNotIn("drop table", schema)
        self.assertNotIn("drop database", schema)


if __name__ == "__main__":
    unittest.main()
