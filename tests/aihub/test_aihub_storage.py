from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.aihub import storage as loader
from src.common.paths import AIHUB_DATABASE_ROOT


class AIHubStorageTests(unittest.TestCase):
    def test_all_managed_tables_are_isolated_by_aihub_prefix(self) -> None:
        self.assertEqual(len(loader.TABLE_FILES), 13)
        self.assertTrue(all(name.startswith("aihub_") for name in loader.TABLE_FILES))
        self.assertEqual(set(loader.TABLE_FILES), set(loader.EXPECTED_COLUMNS))

    def test_schema_contains_only_aihub_create_tables(self) -> None:
        schema = (AIHUB_DATABASE_ROOT / "sql" / "aihub_schema.sql").read_text(
            encoding="utf-8"
        ).lower()

        for table in loader.TABLE_FILES:
            self.assertIn(f"create table if not exists {table}", schema)
        self.assertNotIn("drop database", schema)
        self.assertNotIn("drop table", schema)
        self.assertNotIn("create table if not exists places", schema)

    def test_empty_csv_layout_passes_header_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for table, relative_path in loader.TABLE_FILES.items():
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("w", encoding="utf-8", newline="") as csv_file:
                    csv.writer(csv_file).writerow(loader.EXPECTED_COLUMNS[table])

            counts = loader.validate_input_files(root)

        self.assertEqual(counts, {table: 0 for table in loader.TABLE_FILES})

    def test_batch_reader_converts_only_empty_values_to_none(self) -> None:
        table = "aihub_code_a"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "code_a.csv"
            with path.open("w", encoding="utf-8", newline="") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(loader.EXPECTED_COLUMNS[table])
                writer.writerow(
                    [
                        "1",
                        "VIS",
                        "방문지",
                        "",
                        "",
                        "N",
                        "1",
                        "N",
                        "N",
                        "N",
                        "2026-07-14 00:00:00",
                        "",
                    ]
                )

            rows = list(loader.batched_rows(path, batch_size=10))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0][0], "1")
        self.assertIsNone(rows[0][0][3])
        self.assertIsNone(rows[0][0][-1])

    def test_batch_reader_rejects_non_positive_batch_size(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "code_a.csv"
            with path.open("w", encoding="utf-8", newline="") as csv_file:
                csv.writer(csv_file).writerow(loader.EXPECTED_COLUMNS["aihub_code_a"])

            with self.assertRaisesRegex(ValueError, "batch_size"):
                list(loader.batched_rows(path, batch_size=0))

    def test_replace_delete_order_starts_with_children(self) -> None:
        self.assertLess(
            loader.DELETE_ORDER.index("aihub_activity_consume"),
            loader.DELETE_ORDER.index("aihub_activity"),
        )
        self.assertLess(
            loader.DELETE_ORDER.index("aihub_visit"),
            loader.DELETE_ORDER.index("aihub_travel"),
        )
        self.assertLess(
            loader.DELETE_ORDER.index("aihub_travel"),
            loader.DELETE_ORDER.index("aihub_traveller"),
        )

    def test_aihub_uses_the_shared_tourapi_database(self) -> None:
        environment = {
            "MYSQL_HOST": "127.0.0.1",
            "MYSQL_USER": "tour_app",
            "MYSQL_PASSWORD": "secret-value",
            "MYSQL_DATABASE": "tour_recommender",
        }
        with patch.dict("os.environ", environment, clear=True):
            config = loader.mysql_config_from_env()

        self.assertEqual(config.database, "tour_recommender")
        self.assertNotIn("secret-value", repr(config))

    def test_aihub_schema_does_not_create_or_select_a_database(self) -> None:
        schema = (AIHUB_DATABASE_ROOT / "sql" / "aihub_schema.sql").read_text(
            encoding="utf-8"
        )
        normalized = schema.upper()

        self.assertNotIn("CREATE DATABASE", normalized)
        self.assertNotIn("DROP DATABASE", normalized)
        self.assertNotIn("USE ", normalized)


if __name__ == "__main__":
    unittest.main()
