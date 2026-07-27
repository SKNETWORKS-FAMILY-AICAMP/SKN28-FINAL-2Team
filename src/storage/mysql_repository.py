from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Iterator, Sequence

from src.config.settings import MySQLConfig

from .mysql_mapper import MySQLImportData, build_mysql_import_data


@dataclass(frozen=True)
class MySQLLoadSummary:
    ingestion_run_id: int
    place_count: int
    common_detail_count: int
    intro_detail_count: int
    image_count: int
    search_document_count: int
    search_chunk_count: int
    fetch_record_count: int


class MySQLPlaceRepository:
    def __init__(self, config: MySQLConfig) -> None:
        self.config = config

    @contextmanager
    def connect(self, *, include_database: bool = True) -> Iterator[Any]:
        try:
            import mysql.connector
        except ImportError as exc:
            raise RuntimeError(
                "mysql-connector-python is not installed; run: pip install -r requirements.txt"
            ) from exc
        connection = mysql.connector.connect(
            **self.config.connection_kwargs(include_database=include_database)
        )
        try:
            yield connection
        finally:
            connection.close()

    def ensure_database(self) -> None:
        database = self._validated_database_name()
        with self.connect(include_database=False) as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{database}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
                )
            finally:
                cursor.close()

    def recreate_database(self) -> None:
        database = self._validated_database_name()
        with self.connect(include_database=False) as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")
                cursor.execute(
                    f"CREATE DATABASE `{database}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
                )
            finally:
                cursor.close()

    def apply_schema(self, schema_path: str | Path) -> None:
        self.ensure_database()
        schema_sql = Path(schema_path).read_text(encoding="utf-8")
        with self.connect() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(schema_sql)
                while cursor.nextset():
                    pass
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                cursor.close()

    def load_places(
        self,
        raw_csv_path: str | Path,
        rag_json_path: str | Path,
        *,
        lcls_csv_path: str | Path | None = None,
        rules_path: str | Path | None = None,
        batch_size: int = 200,
    ) -> MySQLLoadSummary:
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")
        data = build_mysql_import_data(
            raw_csv_path,
            rag_json_path,
            lcls_csv_path=lcls_csv_path,
            rules_path=rules_path,
        )
        with self.connect() as connection:
            cursor = connection.cursor()
            run_id = self._start_ingestion_run(cursor, Path(raw_csv_path).name)
            connection.commit()
            try:
                self._upsert_data(cursor, data, run_id, batch_size)
                cursor.execute(
                    "UPDATE ingestion_runs SET status = 'completed', finished_at = %s "
                    "WHERE ingestion_run_id = %s",
                    (datetime.now(), run_id),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                cursor.execute(
                    "UPDATE ingestion_runs SET status = 'failed', finished_at = %s "
                    "WHERE ingestion_run_id = %s",
                    (datetime.now(), run_id),
                )
                connection.commit()
                raise
            finally:
                cursor.close()

        return MySQLLoadSummary(
            ingestion_run_id=run_id,
            place_count=len(data.places),
            common_detail_count=len(data.common_details),
            intro_detail_count=len(data.intro_details),
            image_count=len(data.images),
            search_document_count=len(data.search_documents),
            search_chunk_count=len(data.search_chunks),
            fetch_record_count=len(data.fetch_records),
        )

    def find_rag_content_ids(
        self,
        *,
        datasets: Sequence[str] = (),
        target_collections: Sequence[str] = (),
        place_subtypes: Sequence[str] = (),
        recommendation_scopes: Sequence[str] = (),
        content_type_ids: Sequence[int] = (),
        cities: Sequence[str] = (),
        districts: Sequence[str] = (),
        route_eligible: bool | None = None,
        schedule_eligible: bool | None = None,
        requires_verification: bool | None = None,
        limit: int = 5_000,
    ) -> list[int]:
        """Return IDs that satisfy deterministic itinerary constraints."""

        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        conditions = ["sd.rag_eligible = TRUE"]
        parameters: list[Any] = []

        _append_in_filter(
            conditions, parameters, "sd.document_type", datasets
        )
        _append_in_filter(
            conditions, parameters, "p.content_type_id", content_type_ids
        )
        for column, value in (
            ("sd.route_eligible", route_eligible),
            ("sd.schedule_eligible", schedule_eligible),
            ("sd.requires_verification", requires_verification),
        ):
            if value is not None:
                conditions.append(f"{column} = %s")
                parameters.append(bool(value))

        for prefix, values in (
            ("target_collection", target_collections),
            ("place_subtype", place_subtypes),
            ("recommendation_scope", recommendation_scopes),
        ):
            _append_json_tag_filter(
                conditions,
                parameters,
                [f"{prefix}:{value}" for value in values],
            )

        _append_address_filter(conditions, parameters, cities)
        _append_address_filter(conditions, parameters, districts)

        sql = (
            "SELECT p.content_id "
            "FROM places AS p "
            "JOIN place_search_documents AS sd ON sd.content_id = p.content_id "
            f"WHERE {' AND '.join(conditions)} "
            "ORDER BY p.content_id "
            "LIMIT %s"
        )
        parameters.append(limit)
        with self.connect() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(sql, tuple(parameters))
                return [int(row[0]) for row in cursor.fetchall()]
            finally:
                cursor.close()

    def get_places_by_ids(
        self,
        content_ids: Sequence[int],
        *,
        batch_size: int = 500,
    ) -> list[dict[str, Any]]:
        """Fetch current TourAPI facts for RAG results from MySQL."""

        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")
        normalized_ids = list(dict.fromkeys(int(value) for value in content_ids))
        if not normalized_ids:
            return []

        rows: list[dict[str, Any]] = []
        with self.connect() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                for start in range(0, len(normalized_ids), batch_size):
                    batch = normalized_ids[start : start + batch_size]
                    placeholders = ",".join(["%s"] * len(batch))
                    cursor.execute(
                        _PLACE_DETAILS_SELECT.format(placeholders=placeholders),
                        tuple(batch),
                    )
                    rows.extend(dict(row) for row in cursor.fetchall())
            finally:
                cursor.close()
        return rows

    def get_aihub_evidence(
        self,
        content_ids: Sequence[int],
        *,
        batch_size: int = 500,
    ) -> dict[int, dict[str, Any]]:
        """Return conservative AIHub evidence for confirmed TourAPI mappings."""

        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")
        normalized_ids = list(dict.fromkeys(int(value) for value in content_ids))
        if not normalized_ids:
            return {}

        evidence: dict[int, dict[str, Any]] = {}
        with self.connect() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                if not _has_aihub_mapping_tables(cursor):
                    return {}
                for start in range(0, len(normalized_ids), batch_size):
                    batch = normalized_ids[start : start + batch_size]
                    placeholders = ",".join(["%s"] * len(batch))
                    cursor.execute(
                        _AIHUB_EVIDENCE_SELECT.format(
                            placeholders=placeholders
                        ),
                        tuple(batch),
                    )
                    for row in cursor.fetchall():
                        content_id = int(row["content_id"])
                        evidence[content_id] = {
                            "matched_place_count": int(
                                row["matched_place_count"] or 0
                            ),
                            "visit_count": int(row["visit_count"] or 0),
                            "average_satisfaction": _optional_float(
                                row["average_satisfaction"]
                            ),
                            "average_revisit_intention": _optional_float(
                                row["average_revisit_intention"]
                            ),
                            "average_recommendation_intention": _optional_float(
                                row["average_recommendation_intention"]
                            ),
                            "average_residence_time_min": _optional_float(
                                row["average_residence_time_min"]
                            ),
                        }
            finally:
                cursor.close()
        return evidence

    def _validated_database_name(self) -> str:
        database = self.config.database
        if not database.replace("_", "").isalnum():
            raise ValueError("MYSQL_DATABASE may contain only letters, numbers, and underscores")
        return database

    @staticmethod
    def _start_ingestion_run(cursor: Any, source_name: str) -> int:
        cursor.execute(
            "INSERT INTO ingestion_runs "
            "(source_name, dataset, started_at, status) VALUES (%s, 'all', %s, 'running')",
            (source_name, datetime.now()),
        )
        return int(cursor.lastrowid)

    @staticmethod
    def _upsert_data(
        cursor: Any,
        data: MySQLImportData,
        run_id: int,
        batch_size: int,
    ) -> None:
        _executemany_batches(cursor, _CONTENT_TYPE_UPSERT, data.content_types, batch_size)
        _executemany_batches(cursor, _LCLS_UPSERT, data.lcls_categories, batch_size)
        _executemany_batches(cursor, _PLACE_UPSERT, data.places, batch_size)
        _executemany_batches(cursor, _COMMON_UPSERT, data.common_details, batch_size)
        _executemany_batches(cursor, _INTRO_UPSERT, data.intro_details, batch_size)

        content_ids = [row[0] for row in data.places]
        _delete_by_content_ids(cursor, "place_images", "content_id", content_ids, batch_size)
        _executemany_batches(cursor, _IMAGE_INSERT, data.images, batch_size)
        _executemany_batches(cursor, _SEARCH_DOCUMENT_UPSERT, data.search_documents, batch_size)
        _delete_by_content_ids(
            cursor, "place_search_chunks", "search_document_id", content_ids, batch_size
        )
        _executemany_batches(cursor, _CHUNK_INSERT, data.search_chunks, batch_size)

        fetch_rows = [(run_id, *row) for row in data.fetch_records]
        _executemany_batches(cursor, _FETCH_INSERT, fetch_rows, batch_size)


def _executemany_batches(
    cursor: Any, sql: str, rows: Sequence[tuple[Any, ...]], batch_size: int
) -> None:
    for start in range(0, len(rows), batch_size):
        cursor.executemany(sql, rows[start : start + batch_size])


def _delete_by_content_ids(
    cursor: Any,
    table: str,
    column: str,
    content_ids: Sequence[int],
    batch_size: int,
) -> None:
    for start in range(0, len(content_ids), batch_size):
        batch = content_ids[start : start + batch_size]
        placeholders = ",".join(["%s"] * len(batch))
        cursor.execute(f"DELETE FROM {table} WHERE {column} IN ({placeholders})", batch)


def _append_in_filter(
    conditions: list[str],
    parameters: list[Any],
    column: str,
    values: Sequence[Any],
) -> None:
    if not values:
        return
    placeholders = ",".join(["%s"] * len(values))
    conditions.append(f"{column} IN ({placeholders})")
    parameters.extend(values)


def _append_json_tag_filter(
    conditions: list[str],
    parameters: list[Any],
    tags: Sequence[str],
) -> None:
    if not tags:
        return
    clauses = ["JSON_CONTAINS(sd.tags, %s)" for _ in tags]
    conditions.append(f"({' OR '.join(clauses)})")
    parameters.extend(json.dumps(tag, ensure_ascii=False) for tag in tags)


def _append_address_filter(
    conditions: list[str],
    parameters: list[Any],
    values: Sequence[str],
) -> None:
    if not values:
        return
    clauses: list[str] = []
    for value in values:
        clauses.append("(p.addr1 LIKE %s OR p.addr2 LIKE %s)")
        pattern = f"%{value}%"
        parameters.extend((pattern, pattern))
    conditions.append(f"({' OR '.join(clauses)})")


def _has_aihub_mapping_tables(cursor: Any) -> bool:
    cursor.execute(
        "SELECT COUNT(*) AS table_count "
        "FROM information_schema.tables "
        "WHERE table_schema = DATABASE() "
        "AND table_name IN ('aihub_places', 'aihub_visit')"
    )
    row = cursor.fetchone()
    value = (
        row.get("table_count")
        if isinstance(row, dict)
        else row[0]
    )
    return int(value) == 2


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


_PLACE_DETAILS_SELECT = """
SELECT
    p.content_id,
    p.title,
    p.content_type_id,
    ct.name AS content_type_name,
    p.lcls3_code,
    lc.lcls1_name,
    lc.lcls2_name,
    lc.lcls3_name,
    p.addr1,
    p.addr2,
    p.longitude,
    p.latitude,
    p.api_modified_at AS source_modified_at,
    common.tel,
    common.tel_name,
    common.homepage,
    common.overview,
    intro.info_center,
    intro.opening_hours,
    intro.closed_days,
    intro.parking,
    intro.reservation,
    intro.use_fee,
    intro.check_in_time,
    intro.check_out_time,
    intro.type_details,
    sd.document_type AS dataset,
    sd.rag_eligible,
    sd.route_eligible,
    sd.schedule_eligible,
    sd.requires_verification,
    sd.search_text,
    sd.tags,
    sd.preprocessing_version,
    sd.generated_at,
    (
        SELECT image.image_url
        FROM place_images AS image
        WHERE image.content_id = p.content_id
        ORDER BY image.display_order, image.image_id
        LIMIT 1
    ) AS image_url,
    (
        SELECT MAX(fetch_record.fetched_at)
        FROM api_fetch_records AS fetch_record
        WHERE fetch_record.content_id = p.content_id
          AND fetch_record.fetch_status = 'success'
    ) AS last_fetched_at
FROM places AS p
JOIN content_types AS ct ON ct.content_type_id = p.content_type_id
JOIN lcls_categories AS lc ON lc.lcls3_code = p.lcls3_code
LEFT JOIN place_common_details AS common ON common.content_id = p.content_id
LEFT JOIN place_intro AS intro ON intro.content_id = p.content_id
JOIN place_search_documents AS sd ON sd.content_id = p.content_id
WHERE p.content_id IN ({placeholders})
"""


_AIHUB_EVIDENCE_SELECT = """
SELECT
    mapped.tourapi_content_id AS content_id,
    COUNT(DISTINCT mapped.aihub_place_id) AS matched_place_count,
    COUNT(visit.visit_area_id) AS visit_count,
    AVG(visit.dgstfn) AS average_satisfaction,
    AVG(visit.revisit_intention) AS average_revisit_intention,
    AVG(visit.rcmdtn_intention) AS average_recommendation_intention,
    AVG(visit.residence_time_min) AS average_residence_time_min
FROM aihub_places AS mapped
LEFT JOIN aihub_visit AS visit
    ON visit.aihub_place_id = mapped.aihub_place_id
WHERE mapped.match_status = 'MATCHED'
  AND mapped.tourapi_content_id IN ({placeholders})
GROUP BY mapped.tourapi_content_id
"""


_CONTENT_TYPE_UPSERT = (
    "INSERT INTO content_types (content_type_id, name) VALUES (%s, %s) AS new "
    "ON DUPLICATE KEY UPDATE name = new.name"
)
_LCLS_UPSERT = (
    "INSERT INTO lcls_categories "
    "(lcls3_code, lcls1_code, lcls1_name, lcls2_code, lcls2_name, lcls3_name) "
    "VALUES (%s, %s, %s, %s, %s, %s) AS new ON DUPLICATE KEY UPDATE "
    "lcls1_code = new.lcls1_code, lcls1_name = new.lcls1_name, "
    "lcls2_code = new.lcls2_code, lcls2_name = new.lcls2_name, "
    "lcls3_name = new.lcls3_name"
)
_PLACE_UPSERT = (
    "INSERT INTO places "
    "(content_id, content_type_id, lcls3_code, title, addr1, addr2, area_code, "
    "sigungu_code, zipcode, longitude, latitude, location, map_level, "
    "api_created_at, api_modified_at) VALUES "
    "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
    "ST_GeomFromText(CONCAT('POINT(', %s, ' ', %s, ')'), "
    "4326, 'axis-order=long-lat'), %s, %s, %s) AS new "
    "ON DUPLICATE KEY UPDATE content_type_id = new.content_type_id, "
    "lcls3_code = new.lcls3_code, title = new.title, addr1 = new.addr1, "
    "addr2 = new.addr2, area_code = new.area_code, sigungu_code = new.sigungu_code, "
    "zipcode = new.zipcode, longitude = new.longitude, latitude = new.latitude, "
    "location = new.location, map_level = new.map_level, "
    "api_created_at = new.api_created_at, api_modified_at = new.api_modified_at"
)
_COMMON_UPSERT = (
    "INSERT INTO place_common_details "
    "(content_id, tel, tel_name, homepage, overview, copyright_code) "
    "VALUES (%s, %s, %s, %s, %s, %s) AS new ON DUPLICATE KEY UPDATE "
    "tel = new.tel, tel_name = new.tel_name, homepage = new.homepage, "
    "overview = new.overview, copyright_code = new.copyright_code"
)
_INTRO_UPSERT = (
    "INSERT INTO place_intro "
    "(content_id, info_center, opening_hours, closed_days, parking, reservation, "
    "use_fee, check_in_time, check_out_time, type_details) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) AS new "
    "ON DUPLICATE KEY UPDATE info_center = new.info_center, "
    "opening_hours = new.opening_hours, closed_days = new.closed_days, "
    "parking = new.parking, reservation = new.reservation, use_fee = new.use_fee, "
    "check_in_time = new.check_in_time, check_out_time = new.check_out_time, "
    "type_details = new.type_details"
)
_IMAGE_INSERT = (
    "INSERT INTO place_images "
    "(content_id, image_url, thumbnail_url, image_role, display_order) "
    "VALUES (%s, %s, %s, %s, %s)"
)
_SEARCH_DOCUMENT_UPSERT = (
    "INSERT INTO place_search_documents "
    "(search_document_id, content_id, document_type, rag_eligible, route_eligible, "
    "schedule_eligible, requires_verification, exclusion_reason, search_text, tags, "
    "preprocessing_version, generated_at) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) AS new "
    "ON DUPLICATE KEY UPDATE document_type = new.document_type, "
    "rag_eligible = new.rag_eligible, route_eligible = new.route_eligible, "
    "schedule_eligible = new.schedule_eligible, "
    "requires_verification = new.requires_verification, "
    "exclusion_reason = new.exclusion_reason, search_text = new.search_text, "
    "tags = new.tags, preprocessing_version = new.preprocessing_version, "
    "generated_at = new.generated_at"
)
_CHUNK_INSERT = (
    "INSERT INTO place_search_chunks (search_document_id, chunk_index, chunk_text) "
    "VALUES (%s, %s, %s)"
)
_FETCH_INSERT = (
    "INSERT INTO api_fetch_records "
    "(ingestion_run_id, content_id, endpoint, fetch_status, fetch_error, fetched_at, raw_payload) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s)"
)
