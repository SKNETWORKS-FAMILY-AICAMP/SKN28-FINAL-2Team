from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from src.config.settings import MySQLConfig


TABLE_FILES: dict[str, str] = {
    "aihub_code_a": "code/code_a.csv",
    "aihub_code_b": "code/code_b.csv",
    "aihub_sgg_code": "code/sgg_code.csv",
    "aihub_traveller": "data/jeju_traveller.csv",
    "aihub_travel": "data/jeju_travel.csv",
    "aihub_companion": "data/jeju_companion.csv",
    "aihub_visit": "data/jeju_visit.csv",
    "aihub_activity": "data/jeju_activity.csv",
    "aihub_activity_consume": "data/jeju_activity_consume.csv",
    "aihub_move": "data/jeju_move.csv",
    "aihub_lodge_consume": "data/jeju_lodge_consume.csv",
    "aihub_movement_consume": "data/jeju_movement_consume.csv",
    "aihub_advance_consume": "data/jeju_advance_consume.csv",
}

EXPECTED_COLUMNS: dict[str, tuple[str, ...]] = {
    "aihub_code_a": (
        "idx", "cd_a", "cd_nm", "cd_memo", "cd_memo2", "del_flag",
        "order_num", "perm_write", "perm_edit", "perm_delete", "ins_dt", "edit_dt",
    ),
    "aihub_code_b": (
        "idx", "cd_a", "cd_b", "cd_nm", "cd_memo", "cd_memo2", "del_flag",
        "order_num", "ins_dt", "edit_dt",
    ),
    "aihub_sgg_code": (
        "sgg_cd", "sgg_cd1", "sgg_cd2", "sgg_cd3", "sgg_cd4",
        "sido_nm", "sgg_nm", "dong_nm", "ri_nm",
    ),
    "aihub_traveller": (
        "traveler_id", "residence_sgg_cd", "gender", "age_grp", "edu_nm",
        "edu_fnsh_se", "marr_stts", "family_memb", "job_nm", "job_etc",
        "income", "house_income", "travel_term", "travel_num",
        "travel_like_sido_1", "travel_like_sgg_1", "travel_like_sido_2",
        "travel_like_sgg_2", "travel_like_sido_3", "travel_like_sgg_3",
        "travel_styl_1", "travel_styl_2", "travel_styl_3", "travel_styl_4",
        "travel_styl_5", "travel_styl_6", "travel_styl_7", "travel_styl_8",
        "travel_status_residence", "travel_status_destination",
        "travel_status_accompany", "travel_status_ymd", "travel_motive_1",
        "travel_motive_2", "travel_motive_3", "travel_companions_num",
    ),
    "aihub_travel": (
        "travel_id", "travel_nm", "traveler_id", "travel_purpose",
        "travel_start_ymd", "travel_end_ymd", "mvmn_nm", "travel_persona",
        "travel_mission", "travel_mission_check",
    ),
    "aihub_companion": (
        "companion_seq", "travel_id", "rel_cd", "companion_gender",
        "companion_age_grp", "companion_situation",
    ),
    "aihub_visit": (
        "visit_area_id", "travel_id", "visit_order", "visit_area_nm",
        "visit_start_ymd", "visit_end_ymd", "road_nm_addr", "lotno_addr",
        "x_coord", "y_coord", "road_nm_cd", "lotno_cd", "poi_id", "poi_nm",
        "residence_time_min", "visit_area_type_cd", "revisit_yn",
        "visit_chc_reason_cd", "lodging_type_cd", "dgstfn", "revisit_intention",
        "rcmdtn_intention", "sgg_cd",
    ),
    "aihub_activity": (
        "travel_id", "visit_area_id", "activity_type_cd", "activity_type_seq",
        "activity_etc", "activity_dtl", "rsvt_yn", "expnd_se", "admission_se",
    ),
    "aihub_activity_consume": (
        "travel_id", "visit_area_id", "activity_type_cd", "activity_type_seq",
        "consume_his_seq", "consume_his_sno", "payment_num", "brno", "store_nm",
        "road_nm_addr", "lotno_addr", "road_nm_cd", "lotno_cd", "payment_dt",
        "payment_mthd_se", "payment_amt_won", "payment_etc", "sgg_cd",
    ),
    "aihub_move": (
        "travel_id", "trip_id", "start_visit_area_id", "end_visit_area_id",
        "start_dt_min", "end_dt_min", "mvmn_cd_1", "mvmn_cd_2",
    ),
    "aihub_lodge_consume": (
        "travel_id", "lodging_nm", "lodging_payment_seq", "lodging_type_cd",
        "rsvt_yn", "chk_in_dt_min", "chk_out_dt_min", "payment_num", "brno",
        "store_nm", "road_nm_addr", "lotno_addr", "road_nm_cd", "lotno_cd",
        "payment_dt", "payment_mthd_se", "payment_amt_won", "payment_etc",
    ),
    "aihub_movement_consume": (
        "travel_id", "mvmn_se", "payment_se", "payment_seq", "mvmn_se_nm",
        "rsvt_yn", "payment_num", "brno", "store_nm", "payment_dt",
        "payment_mthd_se", "payment_amt_won", "payment_etc",
    ),
    "aihub_advance_consume": (
        "travel_id", "adv_nm", "adv_seq", "payment_num", "brno", "store_nm",
        "road_nm_addr", "lotno_addr", "road_nm_cd", "lotno_cd", "payment_dt",
        "payment_mthd_se", "payment_amt_won", "payment_etc", "sgg_cd",
    ),
}

DELETE_ORDER = tuple(reversed(tuple(TABLE_FILES)))

INTEGRITY_CHECKS = {
    "travel_without_traveller": """
        SELECT COUNT(*) FROM aihub_travel t
        LEFT JOIN aihub_traveller r ON r.traveler_id = t.traveler_id
        WHERE r.traveler_id IS NULL
    """,
    "visit_without_travel": """
        SELECT COUNT(*) FROM aihub_visit v
        LEFT JOIN aihub_travel t ON t.travel_id = v.travel_id
        WHERE t.travel_id IS NULL
    """,
    "activity_without_visit": """
        SELECT COUNT(*) FROM aihub_activity a
        LEFT JOIN aihub_visit v
          ON v.travel_id = a.travel_id AND v.visit_area_id = a.visit_area_id
        WHERE v.visit_area_id IS NULL
    """,
    "activity_consume_without_activity": """
        SELECT COUNT(*) FROM aihub_activity_consume c
        LEFT JOIN aihub_activity a
          ON a.travel_id = c.travel_id
         AND a.visit_area_id = c.visit_area_id
         AND a.activity_type_cd = c.activity_type_cd
         AND a.activity_type_seq = c.activity_type_seq
        WHERE a.visit_area_id IS NULL
    """,
    "personal_place_visits": """
        SELECT COUNT(*) FROM aihub_visit
        WHERE visit_area_type_cd IN ('21', '22', '23')
    """,
}


def mysql_config_from_env() -> MySQLConfig:
    """Use the same MySQL database as the TourAPI tables."""

    return MySQLConfig.from_env()


def csv_header_and_count(path: Path) -> tuple[tuple[str, ...], int]:
    if not path.exists():
        raise FileNotFoundError(f"AIHub CSV 파일이 없습니다: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.reader(csv_file)
        try:
            header = tuple(next(reader))
        except StopIteration as exc:
            raise ValueError(f"비어 있는 CSV 파일입니다: {path}") from exc
        count = sum(1 for _ in reader)
    return header, count


def validate_input_files(data_root: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table, relative_path in TABLE_FILES.items():
        path = data_root / relative_path
        header, row_count = csv_header_and_count(path)
        expected = EXPECTED_COLUMNS[table]
        if header != expected:
            raise ValueError(
                f"{relative_path} 컬럼이 예상 구조와 다릅니다.\n"
                f"expected={expected}\nactual={header}"
            )
        counts[table] = row_count

    report_path = data_root / "reports" / "preprocessing_report.json"
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        for table, count in counts.items():
            report_name = table.removeprefix("aihub_")
            expected_count = report.get("counts", {}).get(report_name, {}).get(
                "output_rows"
            )
            if expected_count is not None and int(expected_count) != count:
                raise ValueError(
                    f"{table} 행 수가 전처리 보고서와 다릅니다: "
                    f"csv={count}, report={expected_count}"
                )
    return counts


def split_sql_statements(sql_text: str) -> Iterable[str]:
    lines = [
        line for line in sql_text.splitlines() if not line.strip().startswith("--")
    ]
    for statement in "\n".join(lines).split(";"):
        cleaned = statement.strip()
        if cleaned:
            yield cleaned


def batched_rows(path: Path, batch_size: int) -> Iterable[list[tuple[Any, ...]]]:
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.reader(csv_file)
        try:
            next(reader)
        except StopIteration as exc:
            raise ValueError(f"비어 있는 CSV 파일입니다: {path}") from exc
        batch: list[tuple[Any, ...]] = []
        for row in reader:
            batch.append(tuple(None if value == "" else value for value in row))
            if len(batch) >= batch_size:
                yield batch
                batch = []
        if batch:
            yield batch


def connect_mysql(config: MySQLConfig) -> Any:
    try:
        import mysql.connector
    except ImportError as exc:
        raise RuntimeError(
            "mysql-connector-python이 설치되지 않았습니다. "
            "python -m pip install -r requirements.txt 를 먼저 실행하세요."
        ) from exc
    return mysql.connector.connect(**config.connection_kwargs())


def create_tables(connection: Any, schema_file: Path) -> None:
    if not schema_file.exists():
        raise FileNotFoundError(f"스키마 SQL 파일이 없습니다: {schema_file}")
    sql_text = schema_file.read_text(encoding="utf-8")
    with connection.cursor() as cursor:
        for statement in split_sql_statements(sql_text):
            cursor.execute(statement)
    connection.commit()


def ensure_empty_or_replace(connection: Any, replace: bool) -> None:
    with connection.cursor() as cursor:
        counts: dict[str, int] = {}
        for table in TABLE_FILES:
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            counts[table] = int(cursor.fetchone()[0])
        occupied = {table: count for table, count in counts.items() if count}
        if occupied and not replace:
            details = ", ".join(f"{table}={count}" for table, count in occupied.items())
            raise RuntimeError(
                "AIHub 테이블에 이미 데이터가 있습니다. 중복 적재를 막기 위해 중단합니다: "
                + details
                + " (--replace를 명시하면 AIHub 테이블만 다시 적재합니다.)"
            )
        if replace:
            for table in DELETE_ORDER:
                cursor.execute(f"DELETE FROM `{table}`")


def load_table(connection: Any, table: str, path: Path, batch_size: int) -> int:
    if table not in EXPECTED_COLUMNS:
        raise ValueError(f"unmanaged AIHub table: {table}")
    columns = EXPECTED_COLUMNS[table]
    column_sql = ", ".join(f"`{column}`" for column in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    insert_sql = f"INSERT INTO `{table}` ({column_sql}) VALUES ({placeholders})"
    loaded = 0
    with connection.cursor() as cursor:
        for batch in batched_rows(path, batch_size):
            cursor.executemany(insert_sql, batch)
            loaded += len(batch)
    return loaded


def validate_database(
    connection: Any,
    expected_counts: dict[str, int],
) -> dict[str, Any]:
    actual_counts: dict[str, int] = {}
    check_results: dict[str, int] = {}
    with connection.cursor() as cursor:
        for table, expected in expected_counts.items():
            if table not in TABLE_FILES:
                raise ValueError(f"unmanaged AIHub table: {table}")
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            actual = int(cursor.fetchone()[0])
            actual_counts[table] = actual
            if actual != expected:
                raise RuntimeError(f"{table} 행 수 불일치: csv={expected}, mysql={actual}")

        for name, query in INTEGRITY_CHECKS.items():
            cursor.execute(query)
            value = int(cursor.fetchone()[0])
            check_results[name] = value
            if value != 0:
                raise RuntimeError(f"DB 검증 실패: {name}={value}")

    return {"row_counts": actual_counts, "integrity_checks": check_results}


def load_aihub_dataset(
    connection: Any,
    *,
    data_root: Path,
    schema_file: Path,
    replace_existing: bool,
    batch_size: int,
) -> dict[str, Any]:
    """Validate, load, and verify one complete AIHub dataset transaction."""

    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")
    expected_counts = validate_input_files(data_root)
    create_tables(connection, schema_file)
    try:
        ensure_empty_or_replace(connection, replace_existing)
        loaded_counts = {
            table: load_table(
                connection,
                table,
                data_root / relative_path,
                batch_size,
            )
            for table, relative_path in TABLE_FILES.items()
        }
        validation = validate_database(connection, expected_counts)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {"loaded_counts": loaded_counts, **validation}
