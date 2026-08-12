"""Validate production configuration and the initialized RDS databases."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from collections.abc import Mapping
from typing import Any

from dotenv import load_dotenv


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from config.env_validation import validate_production_environment


ACCOUNT_TABLES = {
    "accounts_user",
    "django_migrations",
    "travel_itinerary",
}
TRAVEL_TABLES = {
    "aihub_travel",
    "aihub_visit",
    "package_items",
    "place_images",
    "place_search_documents",
    "places",
    "travel_packages",
}
TRAVEL_COLUMN_CONTRACTS = {
    "travel_packages": {
        "id",
        "package_id",
        "title",
        "summary",
        "region",
        "duration_days",
        "estimated_price",
        "match_profile",
        "is_active",
    },
    "package_items": {
        "id",
        "package_db_id",
        "day_no",
        "sequence",
        "item_type",
        "content_id",
        "stay_minutes",
    },
    "place_images": {
        "content_id",
        "image_url",
        "thumbnail_url",
        "display_order",
    },
    "places": {
        "content_id",
        "title",
        "addr1",
        "addr2",
        "longitude",
        "latitude",
    },
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check production environment values and initialized RDS data."
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=REPOSITORY_ROOT / ".env",
        help="Environment file to load without overriding existing variables.",
    )
    parser.add_argument(
        "--environment-only",
        action="store_true",
        help="Validate environment values without opening a database connection.",
    )
    args = parser.parse_args(argv)

    try:
        if args.env_file.exists():
            load_dotenv(args.env_file, override=False)
        if os.getenv("DJANGO_DEBUG", "true").strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
        }:
            raise ValueError("DJANGO_DEBUG must be false for production verification")
        validate_production_environment(os.environ)

        report: dict[str, Any] = {"environment": "ok"}
        if not args.environment_only:
            report["rds"] = verify_rds(os.environ)
        print(json.dumps({"status": "ok", **report}, ensure_ascii=False, indent=2))
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


def verify_rds(environ: Mapping[str, str]) -> dict[str, Any]:
    try:
        import mysql.connector
    except ImportError as exc:
        raise RuntimeError("mysql-connector-python is not installed") from exc

    connection = mysql.connector.connect(
        host=environ["MYSQL_HOST"],
        port=int(environ["MYSQL_PORT"]),
        user=environ["MYSQL_USER"],
        password=environ["MYSQL_PASSWORD"],
        connection_timeout=int(environ.get("MYSQL_CONNECT_TIMEOUT", "10")),
        charset="utf8mb4",
        use_unicode=True,
    )
    try:
        return _verify_connection(
            connection,
            account_database=environ["ACCOUNT_DB_NAME"],
            travel_database=environ["TRAVEL_DB_NAME"],
        )
    finally:
        connection.close()


def _verify_connection(
    connection: Any,
    *,
    account_database: str,
    travel_database: str,
) -> dict[str, Any]:
    with connection.cursor() as cursor:
        account_present = _table_names(cursor, account_database)
        travel_present = _table_names(cursor, travel_database)
        missing_account = sorted(ACCOUNT_TABLES - account_present)
        missing_travel = sorted(TRAVEL_TABLES - travel_present)
        if missing_account or missing_travel:
            details = []
            if missing_account:
                details.append("account=" + ",".join(missing_account))
            if missing_travel:
                details.append("travel=" + ",".join(missing_travel))
            raise RuntimeError("Missing required RDS tables: " + "; ".join(details))

        missing_columns = {
            table: sorted(required - _column_names(cursor, travel_database, table))
            for table, required in TRAVEL_COLUMN_CONTRACTS.items()
        }
        missing_columns = {
            table: columns for table, columns in missing_columns.items() if columns
        }
        if missing_columns:
            details = "; ".join(
                f"{table}={','.join(columns)}"
                for table, columns in sorted(missing_columns.items())
            )
            raise RuntimeError("Missing required RDS columns: " + details)

        counts = {
            "django_migrations": _scalar(
                cursor, f"SELECT COUNT(*) FROM `{account_database}`.`django_migrations`"
            ),
            "places": _scalar(
                cursor, f"SELECT COUNT(*) FROM `{travel_database}`.`places`"
            ),
            "rag_eligible_documents": _scalar(
                cursor,
                f"SELECT COUNT(*) FROM `{travel_database}`.`place_search_documents` "
                "WHERE rag_eligible = TRUE",
            ),
            "travel_packages": _scalar(
                cursor, f"SELECT COUNT(*) FROM `{travel_database}`.`travel_packages`"
            ),
            "package_items": _scalar(
                cursor, f"SELECT COUNT(*) FROM `{travel_database}`.`package_items`"
            ),
            "aihub_travel": _scalar(
                cursor, f"SELECT COUNT(*) FROM `{travel_database}`.`aihub_travel`"
            ),
            "aihub_visit": _scalar(
                cursor, f"SELECT COUNT(*) FROM `{travel_database}`.`aihub_visit`"
            ),
        }
        empty = sorted(name for name, count in counts.items() if count == 0)
        if empty:
            raise RuntimeError("Required RDS datasets are empty: " + ", ".join(empty))

        integrity = {
            "package_items_without_package": _scalar(
                cursor,
                f"SELECT COUNT(*) FROM `{travel_database}`.`package_items` i "
                f"LEFT JOIN `{travel_database}`.`travel_packages` p "
                "ON p.id = i.package_db_id WHERE p.id IS NULL",
            ),
            "package_items_without_place": _scalar(
                cursor,
                f"SELECT COUNT(*) FROM `{travel_database}`.`package_items` i "
                f"LEFT JOIN `{travel_database}`.`places` p "
                "ON p.content_id = i.content_id WHERE p.content_id IS NULL",
            ),
            "aihub_visits_without_travel": _scalar(
                cursor,
                f"SELECT COUNT(*) FROM `{travel_database}`.`aihub_visit` v "
                f"LEFT JOIN `{travel_database}`.`aihub_travel` t "
                "ON t.travel_id = v.travel_id WHERE t.travel_id IS NULL",
            ),
            "selected_package_foreign_keys": _scalar(
                cursor,
                "SELECT COUNT(*) FROM information_schema.KEY_COLUMN_USAGE "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'travel_itinerary' "
                "AND COLUMN_NAME = 'selected_package_id' "
                "AND REFERENCED_TABLE_NAME IS NOT NULL",
                (account_database,),
            ),
            "migration_0013_applied": _scalar(
                cursor,
                f"SELECT COUNT(*) FROM `{account_database}`.`django_migrations` "
                "WHERE app = 'travel' AND name = '0013_remove_cross_database_package_fk'",
            ),
        }
        failed_integrity = [
            name
            for name, value in integrity.items()
            if (name == "migration_0013_applied" and value != 1)
            or (name != "migration_0013_applied" and value != 0)
        ]
        if failed_integrity:
            details = ", ".join(
                f"{name}={integrity[name]}" for name in failed_integrity
            )
            raise RuntimeError("RDS integrity checks failed: " + details)

        cursor.execute("SELECT VERSION()")
        server_version = str(cursor.fetchone()[0])

    return {
        "server_version": server_version,
        "databases": {
            "account": account_database,
            "travel": travel_database,
        },
        "row_counts": counts,
        "integrity_checks": integrity,
    }


def _table_names(cursor: Any, database: str) -> set[str]:
    cursor.execute(
        "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s",
        (database,),
    )
    return {str(row[0]) for row in cursor.fetchall()}


def _column_names(cursor: Any, database: str, table: str) -> set[str]:
    cursor.execute(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
        (database, table),
    )
    return {str(row[0]) for row in cursor.fetchall()}


def _scalar(cursor: Any, query: str, parameters: tuple[Any, ...] = ()) -> int:
    cursor.execute(query, parameters)
    return int(cursor.fetchone()[0])


if __name__ == "__main__":
    raise SystemExit(main())
