from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.storage.mysql_mapper import (
    build_mysql_import_data,
    parse_datetime,
)
from src.common.paths import TOURAPI_DATABASE_ROOT
from src.config.settings import MySQLConfig, StorageConfigError


class PlaceStorageTests(unittest.TestCase):
    def test_mysql_config_reads_environment_without_exposing_password(self) -> None:
        environment = {
            "MYSQL_USER": "tour_app",
            "MYSQL_PASSWORD": "secret-value",
            "MYSQL_DATABASE": "tour_recommender",
        }
        with patch.dict(os.environ, environment, clear=True):
            config = MySQLConfig.from_env()

        self.assertEqual(config.host, "127.0.0.1")
        self.assertNotIn("secret-value", repr(config))

    def test_mysql_config_rejects_missing_required_values(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(StorageConfigError):
                MySQLConfig.from_env()

    def test_mapper_preserves_all_places_and_marks_excluded_rows(self) -> None:
        rows = [
            _raw_row("1", title="First", image_url="https://example.com/1.jpg"),
            _raw_row("2", title="Second"),
        ]
        rag = {
            "generated_at": "2026-07-14T01:02:03+00:00",
            "preprocessing_version": "places-v2",
            "place_groups": [],
            "documents": [
                {
                    "id": "tourapi:1",
                    "embedding_text": "Place: First. Nature walk.",
                    "metadata": {
                        "contentid": "1",
                        "dataset": "tourism",
                        "target_collection": "attractions",
                        "place_subtype": "attraction",
                        "recommendation_scope": "default",
                        "route_eligible": True,
                        "schedule_eligible": True,
                        "requires_verification": False,
                        "preprocessing_version": "places-v2",
                        "tags": ["nature", "nature"],
                    },
                }
            ],
        }
        rules = {"excluded_content_ids": {"2": "not a tourist stop"}}

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_path = root / "places.csv"
            rag_path = root / "rag.json"
            rules_path = root / "rules.json"
            lcls_path = root / "lcls.csv"
            _write_csv(raw_path, rows)
            _write_csv(lcls_path, [{"code": "NA", "name": "nature tourism"}])
            rag_path.write_text(json.dumps(rag), encoding="utf-8")
            rules_path.write_text(json.dumps(rules), encoding="utf-8")

            data = build_mysql_import_data(
                raw_path,
                rag_path,
                lcls_csv_path=lcls_path,
                rules_path=rules_path,
            )

        self.assertEqual(len(data.places), 2)
        self.assertEqual(len(data.common_details), 2)
        self.assertEqual(len(data.intro_details), 2)
        self.assertEqual(len(data.images), 1)
        self.assertEqual(len(data.search_documents), 2)
        self.assertEqual(len(data.search_chunks), 1)
        self.assertEqual(len(data.fetch_records), 4)
        self.assertEqual(data.lcls_categories[0][2], "nature tourism")
        self.assertEqual(data.intro_details[0][2], "09:00-18:00")
        self.assertTrue(data.search_documents[0][3])
        self.assertFalse(data.search_documents[1][3])
        self.assertEqual(data.search_documents[1][7], "not a tourist stop")
        tags = json.loads(data.search_documents[0][9])
        self.assertEqual(tags.count("nature"), 1)
        self.assertIn("target_collection:attractions", tags)

    def test_schema_matches_tourapi_erd_without_mysql_vectors(self) -> None:
        schema = (
            TOURAPI_DATABASE_ROOT / "mysql_schema.sql"
        ).read_text(encoding="utf-8").lower()

        for table in (
            "content_types",
            "lcls_categories",
            "places",
            "place_common_details",
            "place_intro",
            "place_images",
            "place_search_documents",
            "place_search_chunks",
            "ingestion_runs",
            "api_fetch_records",
        ):
            self.assertIn(f"create table if not exists {table}", schema)
        self.assertNotIn("place_groups", schema)
        self.assertNotIn("place_vector_index_state", schema)
        self.assertNotIn("jsonb", schema)
        self.assertNotIn(" vector ", schema)
        self.assertNotIn("content_id bigint not null unique", schema)

    def test_parse_datetime_normalizes_tourapi_and_iso_values(self) -> None:
        self.assertEqual(parse_datetime("20260714010203").year, 2026)
        self.assertEqual(
            parse_datetime("2026-07-14T01:02:03+00:00").tzinfo,
            None,
        )

def _raw_row(content_id: str, *, title: str, image_url: str = "") -> dict[str, str]:
    return {
        "dataset": "tourism",
        "contentid": content_id,
        "contenttypeid": "12",
        "title": title,
        "common_title": title,
        "common_lclsSystm1": "NA",
        "common_lclsSystm2": "NA01",
        "common_lclsSystm3": "NA010100",
        "common_mapx": "126.5",
        "common_mapy": "33.5",
        "common_createdtime": "20260101000000",
        "common_modifiedtime": "20260714000000",
        "common_firstimage": image_url,
        "common_overview": "Overview",
        "common_fetch_status": "success",
        "intro_usetime": "09:00-18:00",
        "intro_restdate": "Monday",
        "intro_fetch_status": "success",
        "intro_fetched_at": "2026-07-14T00:00:00+00:00",
    }


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
