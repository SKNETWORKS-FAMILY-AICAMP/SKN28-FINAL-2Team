from __future__ import annotations

import unittest

from src.tourapi.crawler.export import combine_dataset_records


class CombineDatasetRecordsTests(unittest.TestCase):
    def test_combines_api_records_without_field_collisions(self) -> None:
        rows = combine_dataset_records(
            dataset="tourism",
            base_records=[
                {"contentid": "1", "contenttypeid": "12", "title": "Base title"}
            ],
            common_records=[
                {"contentid": "1", "contenttypeid": "12", "title": "Common title", "overview": "About"}
            ],
            intro_records=[
                {"contentid": "1", "contenttypeid": "12", "infocenter": "064-000-0000"}
            ],
            info_records=[
                {"contentid": "1", "contenttypeid": "12", "infoname": "A", "infotext": "One"},
                {"contentid": "1", "contenttypeid": "12", "infoname": "B", "infotext": "Two"},
            ],
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["dataset"], "tourism")
        self.assertEqual(rows[0]["title"], "Base title")
        self.assertEqual(rows[0]["common_title"], "Common title")
        self.assertEqual(rows[0]["common_overview"], "About")
        self.assertEqual(rows[0]["intro_infocenter"], "064-000-0000")
        self.assertEqual(len(rows[0]["info_items"]), 2)

    def test_rejects_duplicate_base_content_ids(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate base content ID"):
            combine_dataset_records(
                dataset="food",
                base_records=[{"contentid": "1"}, {"contentid": "1"}],
            )


if __name__ == "__main__":
    unittest.main()
