"""Validate and load preprocessed AIHub Jeju travel logs into MySQL."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from src.aihub.storage import (
    connect_mysql,
    load_aihub_dataset,
    mysql_config_from_env,
    validate_input_files,
)
from src.common.paths import (
    AIHUB_DATA_ROOT,
    AIHUB_DATABASE_ROOT,
    REPOSITORY_ROOT,
)
from src.common.env import load_env_file


DEFAULT_DATA_ROOT = AIHUB_DATA_ROOT / "processed" / "aihub"
DEFAULT_SCHEMA_FILE = AIHUB_DATABASE_ROOT / "sql" / "aihub_schema.sql"

__all__ = [
    "DEFAULT_DATA_ROOT",
    "DEFAULT_SCHEMA_FILE",
    "build_parser",
    "main",
    "parse_args",
    "resolve_data_root",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load AIHub Jeju CSV files into MySQL."
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        help="Directory containing data/, code/, reports/",
    )
    parser.add_argument("--schema-file", type=Path, default=DEFAULT_SCHEMA_FILE)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete only existing aihub_ table rows before loading",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate files and row counts without connecting to MySQL",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Backward-compatible argument parser entry point."""

    return build_parser().parse_args(argv)


def resolve_data_root(argument: Path | None) -> Path:
    if argument is not None:
        return argument.resolve()
    configured = os.getenv("AIHUB_DATA_DIRECTORY")
    if configured:
        path = Path(configured)
        if not path.is_absolute():
            path = REPOSITORY_ROOT / path
        return path.resolve()
    return DEFAULT_DATA_ROOT.resolve()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    load_env_file(REPOSITORY_ROOT / ".env")
    data_root = resolve_data_root(args.data_root)

    if args.dry_run:
        row_counts = validate_input_files(data_root)
        print(
            json.dumps(
                {
                    "status": "dry-run-ok",
                    "data_root": str(data_root),
                    "row_counts": row_counts,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    config = mysql_config_from_env()
    connection = connect_mysql(config)
    try:
        result = load_aihub_dataset(
            connection,
            data_root=data_root,
            schema_file=args.schema_file.resolve(),
            replace_existing=args.replace,
            batch_size=int(os.getenv("AIHUB_LOAD_BATCH_SIZE", "5000")),
        )
    finally:
        connection.close()

    print(json.dumps({"status": "loaded", **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"AIHub MySQL 적재 실패: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
