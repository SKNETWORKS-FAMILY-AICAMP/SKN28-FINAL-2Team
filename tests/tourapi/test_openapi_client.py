from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from urllib.request import Request

from src.tourapi.crawler.openapi_client import (
    OPENAPI_PRESET_GROUPS,
    OpenApiFilterCount,
    OpenApiListFilter,
    _open_with_retries,
    estimate_openapi_call_count,
    _record_matches_region,
)


class OpenApiClientTests(unittest.TestCase):
    @patch("src.tourapi.crawler.openapi_client.time.sleep")
    @patch("src.tourapi.crawler.openapi_client.urlopen")
    def test_retries_connection_reset(self, mock_urlopen, mock_sleep) -> None:
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b"ok"
        mock_urlopen.side_effect = [
            ConnectionResetError(10054, "connection reset by peer"),
            response,
        ]

        body = _open_with_retries(
            Request("https://example.com"),
            timeout=1.0,
            retries=3,
        )

        self.assertEqual(body, b"ok")
        self.assertEqual(mock_urlopen.call_count, 2)
        mock_sleep.assert_called_once_with(1)

    def test_estimates_calls_for_multiple_filters(self) -> None:
        counts = (
            OpenApiFilterCount(OpenApiListFilter("tourism", (("contentTypeId", "12"),)), 356),
            OpenApiFilterCount(OpenApiListFilter("lodging", (("contentTypeId", "32"),)), 220),
            OpenApiFilterCount(OpenApiListFilter("food", (("contentTypeId", "39"),)), 519),
        )

        self.assertEqual(
            estimate_openapi_call_count(
                filter_counts=counts,
                page_size=100,
                detail_mode="list",
            ),
            16,
        )
        self.assertEqual(
            estimate_openapi_call_count(
                filter_counts=counts,
                page_size=100,
                detail_mode="common",
            ),
            1111,
        )

    def test_lcls_presets_match_hub_category_shape(self) -> None:
        tourism = OPENAPI_PRESET_GROUPS["lcls"]["tourism"]
        params = [list_filter.as_params() for list_filter in tourism.list_filters]

        self.assertEqual(
            params,
            [
                {"lclsSystm1": "NA"},
                {"lclsSystm1": "HS"},
                {"lclsSystm1": "EX"},
                {"lclsSystm1": "VE"},
            ],
        )
        self.assertEqual(
            OPENAPI_PRESET_GROUPS["lcls"]["lodging"].list_filters[0].as_params(),
            {"lclsSystm1": "AC"},
        )
        self.assertEqual(
            OPENAPI_PRESET_GROUPS["lcls"]["food"].list_filters[0].as_params(),
            {"lclsSystm1": "FD"},
        )
        self.assertEqual(
            OPENAPI_PRESET_GROUPS["lcls"]["leisure"].list_filters[0].as_params(),
            {"lclsSystm1": "LS"},
        )
        self.assertEqual(
            OPENAPI_PRESET_GROUPS["lcls"]["shopping"].list_filters[0].as_params(),
            {"lclsSystm1": "SH"},
        )

    def test_content_type_presets_include_rag_place_types(self) -> None:
        presets = OPENAPI_PRESET_GROUPS["content-type"]
        self.assertEqual(presets["leisure"].content_type_ids, ("28",))
        self.assertEqual(presets["lodging"].content_type_ids, ("32",))
        self.assertEqual(presets["shopping"].content_type_ids, ("38",))
        self.assertEqual(presets["food"].content_type_ids, ("39",))

    def test_address_region_match_accepts_area_code_or_jeju_address(self) -> None:
        self.assertTrue(
            _record_matches_region(
                {"areacode": "39", "addr1": ""},
                area_code="39",
                address_keywords=("제주특별자치", "제주시", "서귀포시"),
            )
        )
        self.assertTrue(
            _record_matches_region(
                {"areacode": "", "addr1": "제주특별자치도 제주시"},
                area_code="39",
                address_keywords=("제주특별자치", "제주시", "서귀포시"),
            )
        )
        self.assertFalse(
            _record_matches_region(
                {"areacode": "", "addr1": "서울특별시 중구"},
                area_code="39",
                address_keywords=("제주특별자치", "제주시", "서귀포시"),
            )
        )
        self.assertFalse(
            _record_matches_region(
                {"areacode": "35", "addr1": "경상북도 예천군 이미기길 71 제주복집"},
                area_code="39",
                address_keywords=("제주특별자치", "제주시", "서귀포시"),
            )
        )


if __name__ == "__main__":
    unittest.main()
