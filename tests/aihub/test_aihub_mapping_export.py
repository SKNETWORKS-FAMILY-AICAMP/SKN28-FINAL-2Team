from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from src.aihub.mapping_export import EXPORT_COLUMNS, export_mapping_csv


class FakeCursor:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.position = 0
        self.executed_query = ""
        self.closed = False

    def execute(self, query: str) -> None:
        self.executed_query = query

    def fetchmany(self, batch_size: int) -> list[dict[str, object]]:
        batch = self.rows[self.position : self.position + batch_size]
        self.position += len(batch)
        return batch

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.cursor_instance = FakeCursor(rows)

    def cursor(self, *, dictionary: bool = False) -> FakeCursor:
        if not dictionary:
            raise AssertionError("CSV export must request a dictionary cursor")
        return self.cursor_instance


class AIHubMappingExportTests(unittest.TestCase):
    def test_exports_all_columns_with_utf8_bom(self) -> None:
        row = {column: None for column in EXPORT_COLUMNS}
        row.update(
            {
                "aihub_place_id": 1,
                "aihub_place_name": "성산일출봉",
                "aihub_visit_count": 172,
                "match_status": "MATCHED",
                "tourapi_content_id": 126435,
                "tourapi_place_name": "성산일출봉 [유네스코 세계자연유산]",
            }
        )
        connection = FakeConnection([row])

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "mappings.csv"
            count = export_mapping_csv(connection, output, batch_size=1)
            raw = output.read_bytes()
            with output.open(encoding="utf-8-sig", newline="") as csv_file:
                exported = list(csv.DictReader(csv_file))

        self.assertEqual(count, 1)
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(tuple(exported[0]), EXPORT_COLUMNS)
        self.assertEqual(exported[0]["aihub_place_name"], "성산일출봉")
        self.assertEqual(exported[0]["tourapi_content_id"], "126435")
        self.assertIn("LEFT JOIN places", connection.cursor_instance.executed_query)
        self.assertTrue(connection.cursor_instance.closed)

    def test_rejects_non_positive_batch_size(self) -> None:
        with self.assertRaisesRegex(ValueError, "batch_size"):
            export_mapping_csv(FakeConnection([]), "unused.csv", batch_size=0)


if __name__ == "__main__":
    unittest.main()
