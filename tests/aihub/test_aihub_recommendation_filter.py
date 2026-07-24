from __future__ import annotations

import unittest

from src.aihub.recommendation_filter import (
    FranchiseRules,
    NonTourismRules,
    build_recommendation_filter,
    deduplicate_aihub_rows,
    detect_franchise,
)


def rules() -> FranchiseRules:
    return FranchiseRules.from_payload(
        {
            "applicable_visit_area_type_codes": [10, 11],
            "brands": [
                {"name": "스타벅스", "aliases": ["스타벅스", "starbucks"]},
                {"name": "CU", "aliases": ["cu"]},
            ],
        }
    )


def non_tourism_rules() -> NonTourismRules:
    return NonTourismRules.from_payload(
        {
            "transport_visit_area_type_codes": [9],
            "name_keywords": ["렌터카", "버스터미널", "주차장"],
        }
    )


def row(
    place_id: int,
    name: str,
    *,
    address: str = "제주특별자치도 제주시 테스트로 1",
    longitude: str = "126.5",
    latitude: str = "33.5",
    type_code: str = "1",
    visits: int = 1,
    status: str = "UNMATCHED",
    tourapi_content_id: str = "",
) -> dict[str, str]:
    return {
        "aihub_place_id": str(place_id),
        "aihub_place_name": name,
        "aihub_normalized_name": name,
        "aihub_aliases": "[]",
        "aihub_poi_ids": "[]",
        "aihub_road_address": address,
        "aihub_lot_address": "",
        "aihub_longitude": longitude,
        "aihub_latitude": latitude,
        "aihub_visit_area_type_code": type_code,
        "aihub_visit_count": str(visits),
        "aihub_identity_method": "UNIQUE_VISIT",
        "match_status": status,
        "match_method": "NO_RELIABLE_CANDIDATE",
        "name_similarity": "",
        "distance_m": "",
        "confidence_score": "0",
        "tourapi_content_id": tourapi_content_id,
        "tourapi_place_name": "",
        "tourapi_address1": "",
        "tourapi_address2": "",
        "tourapi_longitude": "",
        "tourapi_latitude": "",
        "tourapi_rag_eligible": "",
    }


class AIHubRecommendationFilterTests(unittest.TestCase):
    def test_same_aihub_name_and_address_are_merged(self) -> None:
        rows = [
            row(1, "협재 해수욕장", visits=3),
            row(
                2,
                "협재해수욕장",
                visits=5,
                status="MATCHED",
                tourapi_content_id="127490",
            ),
        ]

        deduplicated = deduplicate_aihub_rows(rows)

        self.assertEqual(len(deduplicated), 1)
        self.assertEqual(deduplicated[0]["aihub_visit_count"], "8")
        self.assertEqual(deduplicated[0]["match_status"], "MATCHED")
        self.assertEqual(deduplicated[0]["merged_aihub_place_ids"], "[1, 2]")

    def test_same_name_at_different_addresses_is_not_merged(self) -> None:
        rows = [
            row(1, "중앙식당", address="제주시 테스트로 1", longitude="126.1"),
            row(2, "중앙식당", address="서귀포시 테스트로 2", longitude="126.8"),
        ]

        self.assertEqual(len(deduplicate_aihub_rows(rows)), 2)

    def test_transport_type_and_food_franchise_are_removed(self) -> None:
        result = build_recommendation_filter(
            [
                row(1, "제주 버스터미널", type_code="9"),
                row(2, "스타벅스 제주점", type_code="11"),
                row(3, "스타벅스 테마호텔", type_code="24"),
                row(4, "독립 카페", type_code="11"),
            ],
            rules(),
            non_tourism_rules(),
        )

        self.assertEqual(result.summary.transport_rows_removed, 1)
        self.assertEqual(result.summary.franchise_rows_removed, 1)
        self.assertEqual(result.summary.recommendation_rows, 2)
        reasons = {item["exclusion_reason"] for item in result.exclusions}
        self.assertEqual(reasons, {"TRANSPORT_TYPE:9", "FRANCHISE:스타벅스"})

    def test_misclassified_rental_car_is_removed_by_narrow_keyword(self) -> None:
        result = build_recommendation_filter(
            [
                row(1, "SK 렌터카 제주지점", type_code="12"),
                row(2, "신신호텔 제주공항점", type_code="24"),
            ],
            rules(),
            non_tourism_rules(),
        )

        self.assertEqual(result.summary.non_tourism_keyword_rows_removed, 1)
        self.assertEqual(result.summary.recommendation_rows, 1)
        self.assertEqual(
            result.exclusions[0]["exclusion_reason"],
            "NON_TOURISM_KEYWORD:렌터카",
        )

    def test_short_ascii_franchise_alias_requires_a_token_boundary(self) -> None:
        franchise_rules = rules()

        self.assertEqual(detect_franchise("CU 제주공항점", franchise_rules), "CU")
        self.assertIsNone(detect_franchise("Scuba 체험장", franchise_rules))


if __name__ == "__main__":
    unittest.main()
