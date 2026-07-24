from __future__ import annotations

import unittest

from src.aihub.tourapi_raw_comparison import (
    RawTourPlace,
    classify_tourapi_against_aihub,
    raw_tour_place_from_row,
)


def aihub_row(
    place_id: int,
    name: str,
    *,
    address: str | None = "제주특별자치도 제주시 테스트로 1",
    longitude: str = "126.5",
    latitude: str = "33.5",
) -> dict[str, str]:
    return {
        "aihub_place_id": str(place_id),
        "aihub_place_name": name,
        "aihub_normalized_name": name,
        "aihub_aliases": "[]",
        "aihub_poi_ids": "[]",
        "aihub_road_address": address or "",
        "aihub_lot_address": "",
        "aihub_longitude": longitude,
        "aihub_latitude": latitude,
        "aihub_visit_area_type_code": "1",
        "aihub_visit_count": "3",
        "aihub_identity_method": "UNIQUE_VISIT",
    }


def tourapi_place(
    content_id: int,
    title: str,
    *,
    address: str = "제주특별자치도 제주시 테스트로 1",
    longitude: float = 126.5,
    latitude: float = 33.5,
) -> RawTourPlace:
    return RawTourPlace(
        content_id=content_id,
        title=title,
        address1=address,
        address2=None,
        longitude=longitude,
        latitude=latitude,
        raw_row={"contentid": str(content_id), "title": title},
    )


class TourApiRawComparisonTests(unittest.TestCase):
    def test_raw_row_prefers_common_detail_values(self) -> None:
        place = raw_tour_place_from_row(
            {
                "contentid": "100",
                "title": "기본 이름",
                "common_title": "상세 이름",
                "addr1": "기본 주소",
                "common_addr1": "상세 주소",
                "mapx": "126.1",
                "mapy": "33.1",
                "common_mapx": "126.2",
                "common_mapy": "33.2",
            }
        )

        self.assertEqual(place.title, "상세 이름")
        self.assertEqual(place.address1, "상세 주소")
        self.assertEqual(place.longitude, 126.2)

    def test_exact_name_and_address_is_matched(self) -> None:
        classified, summary = classify_tourapi_against_aihub(
            [tourapi_place(127490, "협재해수욕장")],
            [aihub_row(1, "협재 해수욕장")],
        )

        self.assertEqual(summary.matched_rows, 1)
        self.assertEqual(classified[0]["aihub_classification"], "MATCHED")
        self.assertEqual(classified[0]["aihub_candidate_place_id"], "1")

    def test_same_address_with_different_name_is_candidate_unmatched(self) -> None:
        classified, summary = classify_tourapi_against_aihub(
            [tourapi_place(1, "TourAPI 관광지")],
            [aihub_row(1, "AIHub 내부 매장")],
        )

        self.assertEqual(summary.aihub_candidate_unmatched_rows, 1)
        self.assertEqual(
            classified[0]["aihub_unmatched_reason"],
            "SAME_ADDRESS_NAME_MISMATCH",
        )

    def test_no_name_address_or_nearby_candidate_is_not_in_aihub(self) -> None:
        classified, summary = classify_tourapi_against_aihub(
            [
                tourapi_place(
                    1,
                    "TourAPI 관광지",
                    address="제주시 서로다른로 2",
                    longitude=126.9,
                )
            ],
            [aihub_row(1, "AIHub 장소", longitude="126.1")],
        )

        self.assertEqual(summary.not_in_aihub_rows, 1)
        self.assertEqual(classified[0]["aihub_classification"], "NOT_IN_AIHUB")
        self.assertEqual(
            classified[0]["aihub_unmatched_reason"],
            "NO_NAME_ADDRESS_OR_NEARBY_CANDIDATE",
        )

    def test_unrelated_nearby_place_is_not_in_aihub(self) -> None:
        classified, summary = classify_tourapi_against_aihub(
            [
                tourapi_place(
                    1,
                    "성읍민속마을",
                    address="제주특별자치도 서귀포시 표선면 성읍리",
                    longitude=126.8000,
                )
            ],
            [
                aihub_row(
                    1,
                    "수스테이",
                    address="제주특별자치도 서귀포시 표선면 성읍리 99",
                    longitude="126.8020",
                )
            ],
        )

        self.assertEqual(summary.not_in_aihub_rows, 1)
        self.assertEqual(classified[0]["aihub_classification"], "NOT_IN_AIHUB")
        self.assertEqual(
            classified[0]["aihub_unmatched_reason"],
            "NEARBY_PLACE_ONLY_NAME_MISMATCH",
        )
        self.assertEqual(classified[0]["aihub_candidate_place_id"], "")


if __name__ == "__main__":
    unittest.main()
