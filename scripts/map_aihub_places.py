"""Create canonical AIHub places and map them to canonical TourAPI places."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any, Iterable


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPOSITORY_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tour_recommender.aihub.place_mapping import (
    GroupedAIHubPlace,
    PlaceMappingResult,
    TourPlaceCandidate,
    TourPlaceMatcher,
    VisitPlaceRecord,
    group_aihub_visits,
)
from tour_recommender.aihub.storage import connect_mysql, split_sql_statements
from tour_recommender.storage.config import MySQLConfig
from tour_recommender.utils.config import load_env_file


DEFAULT_SCHEMA = REPOSITORY_ROOT / "sql" / "aihub_place_mapping.sql"
DEFAULT_RAG_JSON = REPOSITORY_ROOT / "data" / "processed" / "jeju_place_rag_documents.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Group AIHub visits into places and map them to TourAPI."
    )
    parser.add_argument("--env-file", type=Path, default=REPOSITORY_ROOT / ".env")
    parser.add_argument("--schema-file", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--rag-json", type=Path, default=DEFAULT_RAG_JSON)
    parser.add_argument("--batch-size", type=int, default=1000)
    return parser.parse_args()


def fetch_visits(cursor: Any) -> list[VisitPlaceRecord]:
    cursor.execute(
        """
        SELECT travel_id, visit_area_id, visit_area_nm, poi_nm,
               road_nm_addr, lotno_addr, x_coord, y_coord,
               poi_id, visit_area_type_cd
        FROM aihub_visit
        """
    )
    return [
        VisitPlaceRecord(
            travel_id=row[0],
            visit_area_id=row[1],
            name=row[2],
            poi_name=row[3],
            road_address=row[4],
            lot_address=row[5],
            longitude=float(row[6]) if row[6] is not None else None,
            latitude=float(row[7]) if row[7] is not None else None,
            poi_id=row[8],
            visit_area_type_cd=row[9],
        )
        for row in cursor.fetchall()
    ]


def load_tour_candidates(path: Path, eligible_content_ids: set[int]) -> list[TourPlaceCandidate]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("preprocessing_version") != "places-v4":
        raise RuntimeError("TourAPI RAG JSON must use preprocessing_version places-v4")
    candidates: list[TourPlaceCandidate] = []
    for document in payload.get("documents", []):
        metadata = document["metadata"]
        content_id = int(metadata["contentid"])
        if content_id not in eligible_content_ids:
            continue
        candidates.append(
            TourPlaceCandidate(
                content_id=content_id,
                title=metadata["title"],
                aliases=tuple(metadata.get("aliases", [])),
                address=metadata.get("address") or metadata.get("addr1"),
                longitude=_optional_float(metadata.get("longitude")),
                latitude=_optional_float(metadata.get("latitude")),
            )
        )
    if len(candidates) != len(eligible_content_ids):
        raise RuntimeError(
            "RAG JSON and MySQL eligible TourAPI documents differ: "
            f"json={len(candidates)}, mysql={len(eligible_content_ids)}"
        )
    return candidates


def _optional_float(value: Any) -> float | None:
    return float(value) if value not in (None, "") else None


def ensure_schema(connection: Any, schema_path: Path) -> None:
    schema_sql = schema_path.read_text(encoding="utf-8")
    cursor = connection.cursor()
    try:
        for statement in split_sql_statements(schema_sql):
            cursor.execute(statement)
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'aihub_visit'
              AND column_name = 'aihub_place_id'
            """
        )
        if int(cursor.fetchone()[0]) == 0:
            cursor.execute(
                """
                ALTER TABLE aihub_visit
                    ADD COLUMN aihub_place_id BIGINT NULL,
                    ADD INDEX idx_aihub_visit_place (aihub_place_id),
                    ADD CONSTRAINT fk_aihub_visit_place
                        FOREIGN KEY (aihub_place_id)
                        REFERENCES aihub_places (aihub_place_id)
                        ON DELETE SET NULL
                """
            )
        connection.commit()
    finally:
        cursor.close()


def validate_shared_database(cursor: Any) -> None:
    cursor.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = DATABASE()
          AND table_name IN ('places', 'place_search_documents', 'aihub_visit')
        """
    )
    present = {row[0] for row in cursor.fetchall()}
    missing = {"places", "place_search_documents", "aihub_visit"} - present
    if missing:
        raise RuntimeError(
            "The shared database is missing required tables: "
            + ", ".join(sorted(missing))
        )


def batched(values: list[Any], batch_size: int) -> Iterable[list[Any]]:
    for start in range(0, len(values), batch_size):
        yield values[start : start + batch_size]


def place_row(place: GroupedAIHubPlace, match: PlaceMappingResult) -> tuple[Any, ...]:
    return (
        place.aihub_place_id,
        place.canonical_name,
        place.normalized_name,
        json.dumps(place.aliases, ensure_ascii=False),
        json.dumps(place.poi_ids, ensure_ascii=False),
        place.road_address,
        place.lot_address,
        place.longitude,
        place.latitude,
        place.visit_area_type_cd,
        place.visit_count,
        place.identity_method,
        match.tourapi_content_id,
        match.status,
        match.method,
        match.name_similarity,
        match.distance_m,
        match.confidence_score,
    )


INSERT_PLACE_SQL = """
    INSERT INTO aihub_places (
        aihub_place_id, canonical_name, normalized_name, aliases, poi_ids,
        road_nm_addr, lotno_addr, longitude, latitude, visit_area_type_cd,
        visit_count, identity_method, tourapi_content_id, match_status,
        match_method, name_similarity, distance_m, confidence_score
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s, %s, %s
    )
"""


def persist_results(
    connection: Any,
    places: list[GroupedAIHubPlace],
    mappings: list[PlaceMappingResult],
    memberships: dict[tuple[str, str], int],
    batch_size: int,
) -> None:
    mapping_by_place = {mapping.aihub_place_id: mapping for mapping in mappings}
    cursor = connection.cursor()
    try:
        cursor.execute("UPDATE aihub_visit SET aihub_place_id = NULL")
        cursor.execute("DELETE FROM aihub_places")
        rows = [place_row(place, mapping_by_place[place.aihub_place_id]) for place in places]
        for batch in batched(rows, batch_size):
            cursor.executemany(INSERT_PLACE_SQL, batch)
        membership_rows = [
            (place_id, travel_id, visit_area_id)
            for (travel_id, visit_area_id), place_id in memberships.items()
        ]
        update_sql = """
            UPDATE aihub_visit
            SET aihub_place_id = %s
            WHERE travel_id = %s AND visit_area_id = %s
        """
        for batch in batched(membership_rows, batch_size):
            cursor.executemany(update_sql, batch)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


def validate_results(cursor: Any, eligible_content_ids: set[int]) -> dict[str, int]:
    checks: dict[str, int] = {}
    queries = {
        "unlinked_visits": "SELECT COUNT(*) FROM aihub_visit WHERE aihub_place_id IS NULL",
        "visit_without_place": """
            SELECT COUNT(*) FROM aihub_visit v
            LEFT JOIN aihub_places p ON p.aihub_place_id = v.aihub_place_id
            WHERE p.aihub_place_id IS NULL
        """,
        "mapping_without_tourapi": """
            SELECT COUNT(*) FROM aihub_places a
            LEFT JOIN places p ON p.content_id = a.tourapi_content_id
            WHERE a.tourapi_content_id IS NOT NULL AND p.content_id IS NULL
        """,
    }
    for name, query in queries.items():
        cursor.execute(query)
        checks[name] = int(cursor.fetchone()[0])
    if eligible_content_ids:
        placeholders = ",".join(["%s"] * len(eligible_content_ids))
        cursor.execute(
            "SELECT COUNT(*) FROM aihub_places WHERE tourapi_content_id IS NOT NULL "
            f"AND tourapi_content_id NOT IN ({placeholders})",
            tuple(sorted(eligible_content_ids)),
        )
        checks["mapping_to_ineligible_tourapi"] = int(cursor.fetchone()[0])
    if any(checks.values()):
        raise RuntimeError(f"AIHub place mapping integrity check failed: {checks}")
    return checks


def main() -> None:
    args = parse_args()
    if args.batch_size <= 0:
        raise ValueError("--batch-size must be greater than zero")
    load_env_file(args.env_file)
    config = MySQLConfig.from_env()
    connection = connect_mysql(config)
    cursor = connection.cursor()
    try:
        validate_shared_database(cursor)
        ensure_schema(connection, args.schema_file)
        visits = fetch_visits(cursor)
        places, memberships = group_aihub_visits(visits)
        cursor.execute(
            "SELECT content_id FROM place_search_documents WHERE rag_eligible = 1"
        )
        eligible_content_ids = {int(row[0]) for row in cursor.fetchall()}
        tour_candidates = load_tour_candidates(args.rag_json, eligible_content_ids)
        matcher = TourPlaceMatcher(tour_candidates)
        mappings = [matcher.match(place) for place in places]
        persist_results(
            connection,
            places,
            mappings,
            memberships,
            args.batch_size,
        )
        integrity = validate_results(cursor, eligible_content_ids)
        status_counts = Counter(mapping.status for mapping in mappings)
        method_counts = Counter(mapping.method for mapping in mappings)
        identity_counts = Counter(place.identity_method for place in places)
        cursor.execute(
            "SELECT COUNT(DISTINCT tourapi_content_id) FROM aihub_places "
            "WHERE match_status = 'MATCHED'"
        )
        matched_tourapi_places = int(cursor.fetchone()[0])
        print(
            json.dumps(
                {
                    "database": config.database,
                    "source_visit_count": len(visits),
                    "aihub_place_count": len(places),
                    "tourapi_candidate_count": len(tour_candidates),
                    "matched_tourapi_place_count": matched_tourapi_places,
                    "status_counts": dict(sorted(status_counts.items())),
                    "method_counts": dict(sorted(method_counts.items())),
                    "identity_counts": dict(sorted(identity_counts.items())),
                    "integrity_checks": integrity,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":
    main()
