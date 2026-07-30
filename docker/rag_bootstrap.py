"""Initialize the shared MySQL metadata and persistent TourAPI Chroma index."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

from src.aihub.storage import TABLE_FILES, validate_input_files
from src.common.env import load_env_file
from src.config.settings import MySQLConfig


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AIHUB_DATA_ROOT = PROJECT_ROOT / "data" / "processed" / "aihub"
load_env_file(PROJECT_ROOT / ".env")


def _connect() -> Any:
    import mysql.connector

    config = MySQLConfig.from_env()
    return mysql.connector.connect(**config.connection_kwargs())


def wait_for_mysql(timeout_seconds: int = 120) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            connection = _connect()
            connection.close()
            print("[bootstrap] MySQL is ready.", flush=True)
            return
        except Exception as exc:  # MySQL may still be applying its init.
            last_error = exc
            time.sleep(2)
    raise RuntimeError(
        f"MySQL did not become ready within {timeout_seconds}s: {last_error}"
    )


def table_count(table: str) -> int | None:
    if table not in {"places", *TABLE_FILES.keys()}:
        raise ValueError(f"unsupported bootstrap table: {table}")
    try:
        connection = _connect()
        cursor = connection.cursor()
        try:
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            return int(cursor.fetchone()[0])
        finally:
            cursor.close()
            connection.close()
    except Exception:
        return None


def run_command(arguments: list[str]) -> None:
    print("[bootstrap] " + " ".join(arguments), flush=True)
    subprocess.run(arguments, cwd=PROJECT_ROOT, check=True)


def initialize_tourapi(force: bool) -> None:
    existing = table_count("places")
    if existing and not force:
        print(
            f"[bootstrap] TourAPI MySQL already contains {existing} places; "
            "skipping reload.",
            flush=True,
        )
        return
    run_command(
        [
            sys.executable,
            "-m",
            "scripts.storage.manage_tourapi_storage",
            "--env-file",
            "/app/.env.example",
            "mysql-load",
            "--batch-size",
            os.getenv("TOURAPI_LOAD_BATCH_SIZE", "500"),
        ]
    )


def initialize_aihub(force: bool) -> None:
    expected = validate_input_files(AIHUB_DATA_ROOT)
    complete = all(
        table_count(table) == expected_count
        for table, expected_count in expected.items()
    )
    if complete and not force:
        print(
            "[bootstrap] AIHub MySQL tables already match the processed CSVs; "
            "skipping reload.",
            flush=True,
        )
        return
    arguments = [
        sys.executable,
        "-m",
        "scripts.storage.load_aihub_to_mysql",
        "--data-root",
        str(AIHUB_DATA_ROOT),
    ]
    if force or any(table_count(table) not in (None, 0) for table in TABLE_FILES):
        arguments.append("--replace")
    run_command(arguments)


def initialize_chroma(rebuild: bool) -> None:
    arguments = [
        sys.executable,
        "-m",
        "scripts.indexing.build_tourapi_vector_index",
        "--input",
        "/app/data/processed/jeju_place_rag_documents.json",
        "--persist-dir",
        "/app/data/vectorstore",
        "--collection",
        os.getenv("CHROMA_COLLECTION", "jeju_places"),
        "--prune",
    ]
    if rebuild:
        arguments.append("--recreate")
    run_command(arguments)


def main() -> int:
    force_mysql = os.getenv("RAG_DOCKER_FORCE_MYSQL_INIT", "").lower() in {
        "1",
        "true",
        "yes",
    }
    rebuild_chroma = os.getenv(
        "RAG_DOCKER_REBUILD_CHROMA", ""
    ).lower() in {"1", "true", "yes"}
    wait_for_mysql()
    initialize_tourapi(force_mysql)
    initialize_aihub(force_mysql)
    initialize_chroma(rebuild_chroma)
    print("[bootstrap] RAG Docker data initialization is complete.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
