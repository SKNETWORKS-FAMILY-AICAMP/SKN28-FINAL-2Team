"""Export AIHub-to-TourAPI place mappings as a CSV file."""

from __future__ import annotations

import csv
from pathlib import Path
import tempfile
from typing import Any


EXPORT_COLUMNS = (
    "aihub_place_id",
    "aihub_place_name",
    "aihub_normalized_name",
    "aihub_aliases",
    "aihub_poi_ids",
    "aihub_road_address",
    "aihub_lot_address",
    "aihub_longitude",
    "aihub_latitude",
    "aihub_visit_area_type_code",
    "aihub_visit_count",
    "aihub_identity_method",
    "match_status",
    "match_method",
    "name_similarity",
    "distance_m",
    "confidence_score",
    "tourapi_content_id",
    "tourapi_place_name",
    "tourapi_address1",
    "tourapi_address2",
    "tourapi_longitude",
    "tourapi_latitude",
    "tourapi_rag_eligible",
)


MAPPING_EXPORT_QUERY = """
    SELECT
        ap.aihub_place_id,
        ap.canonical_name AS aihub_place_name,
        ap.normalized_name AS aihub_normalized_name,
        ap.aliases AS aihub_aliases,
        ap.poi_ids AS aihub_poi_ids,
        ap.road_nm_addr AS aihub_road_address,
        ap.lotno_addr AS aihub_lot_address,
        ap.longitude AS aihub_longitude,
        ap.latitude AS aihub_latitude,
        ap.visit_area_type_cd AS aihub_visit_area_type_code,
        ap.visit_count AS aihub_visit_count,
        ap.identity_method AS aihub_identity_method,
        ap.match_status,
        ap.match_method,
        ap.name_similarity,
        ap.distance_m,
        ap.confidence_score,
        ap.tourapi_content_id,
        p.title AS tourapi_place_name,
        p.addr1 AS tourapi_address1,
        p.addr2 AS tourapi_address2,
        p.longitude AS tourapi_longitude,
        p.latitude AS tourapi_latitude,
        sd.rag_eligible AS tourapi_rag_eligible
    FROM aihub_places AS ap
    LEFT JOIN places AS p
        ON p.content_id = ap.tourapi_content_id
    LEFT JOIN place_search_documents AS sd
        ON sd.content_id = ap.tourapi_content_id
    ORDER BY
        CASE ap.match_status
            WHEN 'MATCHED' THEN 1
            WHEN 'REVIEW' THEN 2
            ELSE 3
        END,
        ap.visit_count DESC,
        ap.aihub_place_id
"""


def export_mapping_csv(
    connection: Any,
    output_path: str | Path,
    *,
    batch_size: int = 1000,
) -> int:
    """Export every mapping row and return the number of rows written."""

    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")

    destination = Path(output_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    cursor = connection.cursor(dictionary=True)
    temporary_path: Path | None = None
    row_count = 0

    try:
        cursor.execute(MAPPING_EXPORT_QUERY)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8-sig",
            newline="",
            dir=destination.parent,
            prefix=f".{destination.stem}-",
            suffix=".tmp",
            delete=False,
        ) as csv_file:
            temporary_path = Path(csv_file.name)
            writer = csv.DictWriter(csv_file, fieldnames=EXPORT_COLUMNS)
            writer.writeheader()

            while rows := cursor.fetchmany(batch_size):
                writer.writerows(rows)
                row_count += len(rows)

        temporary_path.replace(destination)
        temporary_path = None
    finally:
        cursor.close()
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return row_count
