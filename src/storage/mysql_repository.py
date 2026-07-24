from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
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
