from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from src.storage.mysql_repository import MySQLPlaceRepository
from src.common.paths import (
    REPOSITORY_ROOT,
    TOURAPI_DATABASE_ROOT,
    TOURAPI_DATA_ROOT,
    TOURAPI_SCRIPTS_ROOT,
)
from src.config.settings import MySQLConfig, StorageConfigError
from mysql.connector import Error as MySQLError


DEFAULT_ENV = REPOSITORY_ROOT / ".env"
DEFAULT_RAW = TOURAPI_DATA_ROOT / "raw" / "korea_tour_openapi_jeju_places.csv"
DEFAULT_RAG = TOURAPI_DATA_ROOT / "processed" / "jeju_place_rag_documents.json"
DEFAULT_LCLS = TOURAPI_DATA_ROOT / "raw" / "korea_tour_openapi_lcls_codes.csv"
DEFAULT_RULES = TOURAPI_SCRIPTS_ROOT / "configs" / "place_rules.json"
DEFAULT_SCHEMA = TOURAPI_DATABASE_ROOT / "mysql_schema.sql"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create and load the TourAPI MySQL database."
    )
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    commands = parser.add_subparsers(dest="command", required=True)

    load = commands.add_parser(
        "mysql-load", help="Create schema and load the TourAPI CSV plus RAG JSON."
    )
    load.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    load.add_argument("--rag", type=Path, default=DEFAULT_RAG)
    load.add_argument("--lcls", type=Path, default=DEFAULT_LCLS)
    load.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    load.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    load.add_argument("--batch-size", type=int, default=200)
    load.add_argument(
        "--recreate-database",
        action="store_true",
        help="Drop MYSQL_DATABASE before creating the approved schema.",
    )

    args = parser.parse_args()
    try:
        result = _run(args)
    except (OSError, ValueError, RuntimeError, StorageConfigError, MySQLError) as exc:
        message = str(exc).strip() or exc.__class__.__name__
        print(f"Error: {message}", file=sys.stderr)
        return 1
    _print_json(result)
    return 0


def _run(args: argparse.Namespace) -> object:
    mysql = MySQLPlaceRepository(MySQLConfig.from_env(args.env_file))
    if args.recreate_database:
        mysql.recreate_database()
    mysql.apply_schema(args.schema)
    lcls_csv_path = args.lcls if args.lcls.exists() else None
    return asdict(
        mysql.load_places(
            args.raw,
            args.rag,
            lcls_csv_path=lcls_csv_path,
            rules_path=args.rules,
            batch_size=args.batch_size,
        )
    )


def _print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    raise SystemExit(main())
