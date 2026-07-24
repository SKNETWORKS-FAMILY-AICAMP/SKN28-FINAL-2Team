from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts.crawler.fetch_lcls_codes import build_parser
from src.tourapi.crawler.lcls import fetch_lcls_code_tree
from src.tourapi.crawler.openapi_client import OpenApiError


class LclsCodeTests(unittest.TestCase):
    def test_cli_defaults_to_complete_tree_and_csv_only(self) -> None:
        args = build_parser().parse_args([])

        self.assertEqual(args.depth, 3)
        self.assertFalse(args.json)

    @patch(
        "src.tourapi.crawler.lcls."
        "fetch_lcls_code_records"
    )
    def test_fetches_all_three_levels(self, mock_fetch) -> None:
        def fake_fetch(*_args, query_params=None, **_kwargs):
            query = query_params or {}
            if not query:
                return [{"code": "NA", "name": "자연관광"}], 1
            if query == {"lclsSystm1": "NA"}:
                return [{"code": "NA01", "name": "자연"}], 1
            if query == {"lclsSystm1": "NA", "lclsSystm2": "NA01"}:
                return [{"code": "NA010100", "name": "자연관광지"}], 1
            self.fail(f"unexpected LCLS query: {query}")

        mock_fetch.side_effect = fake_fetch

        result = fetch_lcls_code_tree(service_key="test-key")

        self.assertEqual(result.max_depth, 3)
        self.assertEqual(result.calls_used, 3)
        self.assertEqual(
            [record["_query_depth"] for record in result.records],
            [1, 2, 3],
        )
        self.assertEqual(result.records[-1]["code"], "NA010100")

    @patch(
        "src.tourapi.crawler.lcls."
        "fetch_lcls_code_records"
    )
    def test_stops_before_exceeding_call_budget(self, mock_fetch) -> None:
        mock_fetch.side_effect = [
            ([{"code": "NA"}], 1),
            ([{"code": "NA01"}], 1),
        ]

        with self.assertRaisesRegex(OpenApiError, "call budget"):
            fetch_lcls_code_tree(service_key="test-key", call_budget=2)


if __name__ == "__main__":
    unittest.main()
