"""Apply the versioned package catalog migration once."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any

from src.common.env import load_env_file
from src.common.paths import REPOSITORY_ROOT
from src.config.settings import MySQLConfig
from src.storage.mysql_repository import MySQLPlaceRepository


MIGRATION_NAME = "20260818_package_companion_tags_50"
DEFAULT_MIGRATION = (
    REPOSITORY_ROOT
    / "generated_packages.100.json"
    / "migrate_package_companion_tags_50.sql"
)
MIGRATION_TABLE = "tourmain_catalog_migrations"
REQUIRED_COLUMNS = {
    "travel_packages": {"companion", "tags"},
    "package_items": {"tags"},
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=REPOSITORY_ROOT / ".env")
    parser.add_argument("--migration-file", type=Path, default=DEFAULT_MIGRATION)
    args = parser.parse_args(argv)

    try:
        load_env_file(args.env_file)
        repository = MySQLPlaceRepository(MySQLConfig.from_env())
        result = migrate_package_catalog(repository, args.migration_file)
        print(json.dumps({"status": "ok", **result}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {"status": "failed", "error": str(exc) or exc.__class__.__name__},
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1


def migrate_package_catalog(
    repository: MySQLPlaceRepository,
    migration_path: Path,
) -> dict[str, str]:
    checksum = _migration_checksum(migration_path)
    with repository.connect() as connection:
        _ensure_migration_table(connection)
        applied_checksum = _applied_checksum(connection)
        if applied_checksum is not None:
            if applied_checksum != checksum:
                raise RuntimeError(
                    f"Catalog migration checksum changed: {MIGRATION_NAME}"
                )
            _verify_required_columns(connection)
            return {"migration": MIGRATION_NAME, "result": "already_applied"}

    repository.apply_schema(migration_path)

    with repository.connect() as connection:
        _verify_required_columns(connection)
        _record_migration(connection, checksum)
    return {"migration": MIGRATION_NAME, "result": "applied"}


def _migration_checksum(migration_path: Path) -> str:
    return sha256(migration_path.read_bytes()).hexdigest()


def _ensure_migration_table(connection: Any) -> None:
    cursor = connection.cursor()
    try:
        cursor.execute(
            f"CREATE TABLE IF NOT EXISTS `{MIGRATION_TABLE}` ("
            "name VARCHAR(191) PRIMARY KEY, "
            "checksum CHAR(64) NOT NULL, "
            "applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
        )
        connection.commit()
    finally:
        cursor.close()


def _applied_checksum(connection: Any) -> str | None:
    cursor = connection.cursor()
    try:
        cursor.execute(
            f"SELECT checksum FROM `{MIGRATION_TABLE}` WHERE name = %s",
            (MIGRATION_NAME,),
        )
        row = cursor.fetchone()
        return None if row is None else str(row[0])
    finally:
        cursor.close()


def _verify_required_columns(connection: Any) -> None:
    missing: dict[str, list[str]] = {}
    cursor = connection.cursor()
    try:
        for table, required in REQUIRED_COLUMNS.items():
            cursor.execute(f"SHOW COLUMNS FROM `{table}`")
            columns = {str(row[0]) for row in cursor.fetchall()}
            if absent := sorted(required - columns):
                missing[table] = absent
    finally:
        cursor.close()
    if missing:
        details = "; ".join(
            f"{table}={','.join(columns)}" for table, columns in sorted(missing.items())
        )
        raise RuntimeError("Catalog migration left missing columns: " + details)


def _record_migration(connection: Any, checksum: str) -> None:
    cursor = connection.cursor()
    try:
        cursor.execute(
            f"INSERT INTO `{MIGRATION_TABLE}` (name, checksum) VALUES (%s, %s)",
            (MIGRATION_NAME, checksum),
        )
        connection.commit()
    finally:
        cursor.close()


if __name__ == "__main__":
    raise SystemExit(main())
