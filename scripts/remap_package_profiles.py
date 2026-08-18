"""Generate or apply the travel_packages companion/tags column migration."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.common.env import load_env_file
from src.config.settings import MySQLConfig
from src.recommender.profile_mapping import (
    COMPANION_ORDER,
    ITEM_TAG_ORDER,
    PACKAGE_TAG_ORDER,
    item_categories_from_tags,
    normalize_companion_types,
    package_categories_from_tags,
    serialize_csv_values,
)


DEFAULT_ENV = PROJECT_ROOT.parent / ".mysql-local-admin.env"
DEFAULT_SQL = PROJECT_ROOT / "scripts" / "sql" / "migrate_package_companion_tags_50.sql"
DEFAULT_BACKUP = PROJECT_ROOT / "outputs" / "package_columns_before_companion_tags.json"
LEGACY_COMPANION_FLAGS = {
    "solo": "companion_solo",
    "friend": "companion_friend",
    "couple": "companion_couple",
    "family": "companion_family",
}
LEGACY_TAG_FLAGS = {
    "nature": "tag_nature",
    "culture": "tag_culture",
    "festival": "tag_festival",
    "experience": "tag_experience",
    "food": "tag_food",
    "cafe": "tag_cafe",
    "activity": "tag_activity",
    "shopping": "tag_shopping",
}
LEGACY_COLUMNS = tuple(LEGACY_COMPANION_FLAGS.values()) + tuple(
    LEGACY_TAG_FLAGS.values()
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--output-sql", type=Path, default=DEFAULT_SQL)
    parser.add_argument("--backup", type=Path, default=DEFAULT_BACKUP)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    config = _database_config(args.env_file)
    values = _load_values(config)
    if not values["packages"]:
        raise ValueError("no active travel packages were found")
    args.output_sql.parent.mkdir(parents=True, exist_ok=True)
    args.output_sql.write_text(_render_sql(values), encoding="utf-8")
    if args.apply:
        args.backup.parent.mkdir(parents=True, exist_ok=True)
        args.backup.write_text(
            json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8-sig"
        )
        _apply(config, values)
    print(
        json.dumps(
            {
                "package_count": len(values["packages"]),
                "item_count": len(values["items"]),
                "sql_path": str(args.output_sql),
                "backup_path": str(args.backup) if args.apply else None,
                "database_updated": args.apply,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _database_config(env_file: Path) -> MySQLConfig:
    load_env_file(env_file)
    for standard, admin in {
        "MYSQL_HOST": "MYSQL_ADMIN_HOST",
        "MYSQL_PORT": "MYSQL_ADMIN_PORT",
        "MYSQL_USER": "MYSQL_ADMIN_USER",
        "MYSQL_PASSWORD": "MYSQL_ADMIN_PASSWORD",
    }.items():
        if not os.environ.get(standard) and os.environ.get(admin):
            os.environ[standard] = os.environ[admin]
    if not os.environ.get("MYSQL_DATABASE") and os.environ.get("TRAVEL_DB_NAME"):
        os.environ["MYSQL_DATABASE"] = os.environ["TRAVEL_DB_NAME"]
    return MySQLConfig.from_env()


def _load_values(config: MySQLConfig) -> dict[str, dict[Any, dict[str, str]]]:
    import mysql.connector

    with mysql.connector.connect(**config.connection_kwargs()) as connection:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute("SHOW COLUMNS FROM travel_packages")
            columns = {str(row["Field"]) for row in cursor.fetchall()}
            packages: dict[str, dict[str, str]] = {}
            if "companion" in columns:
                cursor.execute(
                    "SELECT package_id, companion FROM travel_packages "
                    "WHERE is_active = TRUE ORDER BY id"
                )
                for row in cursor.fetchall():
                    packages[str(row["package_id"])] = {
                        "companion": str(row.get("companion") or ""),
                        "tags": "",
                    }
            elif set(LEGACY_COLUMNS).issubset(columns):
                cursor.execute(
                    "SELECT package_id, " + ", ".join(LEGACY_COLUMNS)
                    + " FROM travel_packages WHERE is_active = TRUE ORDER BY id"
                )
                for row in cursor.fetchall():
                    companions = [
                        name for name, column in LEGACY_COMPANION_FLAGS.items()
                        if bool(row[column])
                    ]
                    packages[str(row["package_id"])] = {
                        "companion": serialize_csv_values(companions, COMPANION_ORDER),
                        "tags": "",
                    }
            elif "match_profile" in columns:
                cursor.execute(
                    "SELECT package_id, match_profile FROM travel_packages "
                    "WHERE is_active = TRUE ORDER BY id"
                )
                for row in cursor.fetchall():
                    profile = row.get("match_profile") or {}
                    profile = json.loads(profile) if isinstance(profile, str) else profile
                    companions = normalize_companion_types(
                        profile.get("companion_types")
                        or profile.get("party_types")
                        or profile.get("party_type")
                    )
                    packages[str(row["package_id"])] = {
                        "companion": serialize_csv_values(companions, COMPANION_ORDER),
                        "tags": "",
                    }
            else:
                raise ValueError("no supported package profile columns were found")

            cursor.execute(
                """
                SELECT tp.package_id, pi.content_id, sd.tags
                FROM travel_packages tp
                JOIN package_items pi ON pi.package_db_id = tp.id
                LEFT JOIN place_search_documents sd ON sd.content_id = pi.content_id
                WHERE tp.is_active = TRUE
                ORDER BY tp.id, pi.day_no, pi.sequence, pi.id
                """
            )
            package_tag_sets: dict[str, set[str]] = {
                package_id: set() for package_id in packages
            }
            items: dict[str, dict[str, Any]] = {}
            for row in cursor.fetchall():
                package_id = str(row["package_id"])
                raw_tags = row.get("tags") or []
                tags = json.loads(raw_tags) if isinstance(raw_tags, str) else raw_tags
                package_tag_sets[package_id].update(package_categories_from_tags(tags))
                content_id = int(row["content_id"])
                items[f"{package_id}:{content_id}"] = {
                    "package_id": package_id,
                    "content_id": content_id,
                    "tags": serialize_csv_values(
                        item_categories_from_tags(tags), ITEM_TAG_ORDER
                    )
                }
            for package_id, tag_values in package_tag_sets.items():
                packages[package_id]["tags"] = serialize_csv_values(
                    tag_values, PACKAGE_TAG_ORDER
                )
            return {"packages": packages, "items": items}
        finally:
            cursor.close()


def _render_sql(values: dict[str, dict[Any, dict[str, str]]]) -> str:
    packages = values["packages"]
    items = values["items"]
    lines = [
        "-- Stores companion/package tags on packages and subtype tags on each item.",
        *_conditional_add("companion", "VARCHAR(100) NOT NULL DEFAULT ''"),
        *_conditional_add("tags", "VARCHAR(255) NOT NULL DEFAULT ''"),
        *_conditional_add(
            "tags", "VARCHAR(100) NOT NULL DEFAULT ''", table="package_items"
        ),
        "START TRANSACTION;",
        "",
    ]
    for package_id, row in packages.items():
        lines.extend(
            [
                "UPDATE travel_packages",
                f"SET companion = '{_escape(row['companion'])}',",
                f"    tags = '{_escape(row['tags'])}'",
                f"WHERE package_id = '{_escape(package_id)}';",
                "",
            ]
        )
    for row in items.values():
        lines.extend(
            [
                "UPDATE package_items AS pi",
                "JOIN travel_packages AS tp ON tp.id = pi.package_db_id",
                f"SET pi.tags = '{_escape(row['tags'])}'",
                f"WHERE tp.package_id = '{_escape(str(row['package_id']))}'",
                f"  AND pi.content_id = {int(row['content_id'])};",
                "",
            ]
        )
    lines.extend(["COMMIT;", ""])
    for column in ("match_profile", *LEGACY_COLUMNS):
        lines.extend(_conditional_drop(column))
    lines.extend(
        [
            "SELECT package_id, companion, tags",
            "FROM travel_packages",
            "WHERE is_active = TRUE",
            "ORDER BY id;",
            "",
            "SELECT id, package_db_id, content_id, tags",
            "FROM package_items",
            "ORDER BY id;",
            "",
        ]
    )
    return "\n".join(lines)


def _conditional_add(
    column: str, definition: str, *, table: str = "travel_packages"
) -> list[str]:
    return _conditional_ddl(
        column,
        f"ALTER TABLE {table} ADD COLUMN {column} {definition}",
        when_exists=False,
        table=table,
    )


def _conditional_drop(column: str) -> list[str]:
    return _conditional_ddl(
        column,
        f"ALTER TABLE travel_packages DROP COLUMN {column}",
        when_exists=True,
        table="travel_packages",
    )


def _conditional_ddl(
    column: str, ddl: str, *, when_exists: bool, table: str
) -> list[str]:
    operator = "= 1" if when_exists else "= 0"
    return [
        "SET @package_ddl = (",
        f"    SELECT IF(COUNT(*) {operator}, '{_escape(ddl)}', 'SELECT 1')",
        "    FROM information_schema.COLUMNS",
        f"    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '{table}'",
        f"      AND COLUMN_NAME = '{column}'",
        ");",
        "PREPARE package_stmt FROM @package_ddl;",
        "EXECUTE package_stmt;",
        "DEALLOCATE PREPARE package_stmt;",
        "",
    ]


def _apply(config: MySQLConfig, values: dict[str, dict[Any, dict[str, str]]]) -> None:
    import mysql.connector

    with mysql.connector.connect(**config.connection_kwargs()) as connection:
        cursor = connection.cursor()
        try:
            cursor.execute("SHOW COLUMNS FROM travel_packages")
            columns = {str(row[0]) for row in cursor.fetchall()}
            if "companion" not in columns:
                cursor.execute(
                    "ALTER TABLE travel_packages ADD COLUMN companion "
                    "VARCHAR(100) NOT NULL DEFAULT ''"
                )
            if "tags" not in columns:
                cursor.execute(
                    "ALTER TABLE travel_packages ADD COLUMN tags "
                    "VARCHAR(255) NOT NULL DEFAULT ''"
                )
            cursor.execute("SHOW COLUMNS FROM package_items")
            item_columns = {str(row[0]) for row in cursor.fetchall()}
            if "tags" not in item_columns:
                cursor.execute(
                    "ALTER TABLE package_items ADD COLUMN tags "
                    "VARCHAR(100) NOT NULL DEFAULT ''"
                )
            cursor.executemany(
                "UPDATE travel_packages SET companion=%s, tags=%s WHERE package_id=%s",
                [
                    (row["companion"], row["tags"], package_id)
                    for package_id, row in values["packages"].items()
                ],
            )
            cursor.executemany(
                "UPDATE package_items AS pi "
                "JOIN travel_packages AS tp ON tp.id = pi.package_db_id "
                "SET pi.tags=%s WHERE tp.package_id=%s AND pi.content_id=%s",
                [
                    (row["tags"], row["package_id"], row["content_id"])
                    for row in values["items"].values()
                ],
            )
            connection.commit()
            for column in ("match_profile", *LEGACY_COLUMNS):
                if column in columns:
                    cursor.execute(f"ALTER TABLE travel_packages DROP COLUMN {column}")
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "''")


if __name__ == "__main__":
    raise SystemExit(main())
