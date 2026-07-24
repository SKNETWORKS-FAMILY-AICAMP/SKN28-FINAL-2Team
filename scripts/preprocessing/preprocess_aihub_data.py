"""Command-line entry point for AIHub preprocessing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.aihub.preprocessing import (
    DEFAULT_DATASET_ROOT,
    DEFAULT_OUTPUT_ROOT,
    preprocess,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preprocess AIHub domestic travel logs for Jeju."
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=DEFAULT_DATASET_ROOT,
        help=(
            "AIHub dataset root containing 3.개방데이터/1.데이터 "
            f"(default: {DEFAULT_DATASET_ROOT})"
        ),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help=f"Output directory (default: {DEFAULT_OUTPUT_ROOT})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = preprocess(args.dataset_root.resolve(), args.output_root.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
