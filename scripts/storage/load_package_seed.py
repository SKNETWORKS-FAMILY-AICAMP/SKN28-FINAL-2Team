"""Load the bundled package seed only into a verified empty catalog."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
import sys

from src.common.env import load_env_file
from src.common.paths import REPOSITORY_ROOT
from src.config.settings import MySQLConfig
from src.storage.mysql_repository import MySQLPlaceRepository


DEFAULT_SEED = REPOSITORY_ROOT / "src" / "storage" / "seed" / "package_seed.sql"
DEFAULT_COMPATIBILITY_MIGRATION = (
    REPOSITORY_ROOT
    / "generated_packages.100.json"
    / "migrate_package_companion_tags_50.sql"
)
_CONTENT_ID = re.compile(
    r"\(\d+,\d+,(?:NULL|\d+),(?:NULL|\d+),'(?:tourism|restaurant|hotel)',(\d+),"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load the initial travel package seed.")
    parser.add_argument("--env-file", type=Path, default=REPOSITORY_ROOT / ".env")
    parser.add_argument("--seed-file", type=Path, default=DEFAULT_SEED)
    parser.add_argument(
        "--compatibility-migration",
        type=Path,
        default=DEFAULT_COMPATIBILITY_MIGRATION,
    )
    parser.add_argument(
        "--confirm-empty-database",
        action="store_true",
        required=True,
        help="Required acknowledgement that package tables must not already exist.",
    )
    args = parser.parse_args(argv)

    try:
        load_env_file(args.env_file)
        config = MySQLConfig.from_env()
        repository = MySQLPlaceRepository(config)
        seed_sql = args.seed_file.read_text(encoding="utf-8")
        args.compatibility_migration.read_text(encoding="utf-8")
        content_ids = {int(value) for value in _CONTENT_ID.findall(seed_sql)}
        if not content_ids:
            raise RuntimeError("No package item content IDs were found in the seed file")

        with repository.connect() as connection:
            _ensure_target_is_empty(connection, config.database)
            missing_content_ids = _missing_content_ids(connection, content_ids)
            if missing_content_ids:
                preview = ", ".join(str(value) for value in missing_content_ids[:10])
                raise RuntimeError(
                    f"Package seed references {len(missing_content_ids)} missing places: {preview}"
                )

        repository.apply_schema(args.seed_file)
        repository.apply_schema(args.compatibility_migration)
        result = _verify_loaded_seed(repository)
        print(json.dumps({"status": "loaded", **result}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"Error: {str(exc) or exc.__class__.__name__}", file=sys.stderr)
        return 1


def _ensure_target_is_empty(connection, database: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT TABLE_NAME FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = %s "
            "AND TABLE_NAME IN ('travel_packages', 'package_items')",
            (database,),
        )
        existing = sorted(str(row[0]) for row in cursor.fetchall())
    if existing:
        raise RuntimeError(
            "Refusing to run destructive package seed; tables already exist: "
            + ", ".join(existing)
        )


def _missing_content_ids(connection, content_ids: set[int]) -> list[int]:
    present: set[int] = set()
    ordered = sorted(content_ids)
    with connection.cursor() as cursor:
        for start in range(0, len(ordered), 500):
            batch = ordered[start : start + 500]
            placeholders = ",".join(["%s"] * len(batch))
            cursor.execute(
                f"SELECT content_id FROM places WHERE content_id IN ({placeholders})",
                tuple(batch),
            )
            present.update(int(row[0]) for row in cursor.fetchall())
    return sorted(content_ids - present)


def _verify_loaded_seed(repository: MySQLPlaceRepository) -> dict[str, int]:
    with repository.connect() as connection, connection.cursor() as cursor:
        for table, required_columns in {
            "travel_packages": {"companion", "tags"},
            "package_items": {"tags"},
        }.items():
            cursor.execute(f"SHOW COLUMNS FROM `{table}`")
            columns = {str(row[0]) for row in cursor.fetchall()}
            missing = sorted(required_columns - columns)
            if missing:
                raise RuntimeError(
                    f"Package seed is missing required {table} columns: "
                    + ", ".join(missing)
                )
        cursor.execute("SELECT COUNT(*) FROM travel_packages")
        package_count = int(cursor.fetchone()[0])
        cursor.execute("SELECT COUNT(*) FROM package_items")
        item_count = int(cursor.fetchone()[0])
        cursor.execute(
            "SELECT COUNT(*) FROM package_items i "
            "LEFT JOIN places p ON p.content_id = i.content_id "
            "WHERE p.content_id IS NULL"
        )
        orphan_place_count = int(cursor.fetchone()[0])
        cursor.execute(
            "SELECT COUNT(*) FROM package_items i "
            "LEFT JOIN travel_packages p ON p.id = i.package_db_id "
            "WHERE p.id IS NULL"
        )
        orphan_package_count = int(cursor.fetchone()[0])
    if (
        not package_count
        or not item_count
        or orphan_place_count
        or orphan_package_count
    ):
        raise RuntimeError(
            "Package seed verification failed: "
            f"packages={package_count}, items={item_count}, "
            f"place_orphans={orphan_place_count}, "
            f"package_orphans={orphan_package_count}"
        )
    return {
        "travel_packages": package_count,
        "package_items": item_count,
        "orphan_places": orphan_place_count,
        "orphan_packages": orphan_package_count,
    }


if __name__ == "__main__":
    raise SystemExit(main())
