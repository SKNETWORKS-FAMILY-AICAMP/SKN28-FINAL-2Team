"""Command-line entry point for AIHub-to-TourAPI place mapping."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.aihub.mapping_pipeline import (
    DEFAULT_RAG_JSON,
    DEFAULT_SCHEMA,
    load_tour_candidates,
    run_mapping,
)
from src.common.env import load_env_file
from src.common.paths import REPOSITORY_ROOT
from src.config.settings import MySQLConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Group AIHub visits into places and map them to TourAPI."
    )
    parser.add_argument("--env-file", type=Path, default=REPOSITORY_ROOT / ".env")
    parser.add_argument("--schema-file", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--rag-json", type=Path, default=DEFAULT_RAG_JSON)
    parser.add_argument("--batch-size", type=int, default=1000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_env_file(args.env_file)
    report = run_mapping(
        MySQLConfig.from_env(),
        schema_path=args.schema_file,
        rag_json=args.rag_json,
        batch_size=args.batch_size,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
