"""Export all AIHub-to-TourAPI place mapping results to CSV."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from src.aihub.storage import connect_mysql
from src.aihub.mapping_export import export_mapping_csv
from src.common.paths import AIHUB_EXPORT_ROOT, REPOSITORY_ROOT
from src.config.settings import MySQLConfig
from src.common.env import load_env_file


DEFAULT_OUTPUT = AIHUB_EXPORT_ROOT / "aihub_tourapi_place_mappings.csv"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export all AIHub-to-TourAPI place mappings to CSV."
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=REPOSITORY_ROOT / ".env",
        help="MySQL environment file (default: project .env)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"CSV destination (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Rows fetched from MySQL per batch (default: 1000)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_env_file(args.env_file)
    config = MySQLConfig.from_env()
    connection = connect_mysql(config)
    try:
        row_count = export_mapping_csv(
            connection,
            args.output,
            batch_size=args.batch_size,
        )
    finally:
        connection.close()

    print(
        json.dumps(
            {
                "status": "exported",
                "database": config.database,
                "row_count": row_count,
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"AIHub mapping CSV export failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
