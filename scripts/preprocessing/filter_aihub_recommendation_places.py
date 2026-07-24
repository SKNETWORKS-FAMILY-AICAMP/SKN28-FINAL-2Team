"""Create tourism recommendation candidates from the AIHub mapping CSV."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from src.aihub.recommendation_csv import (
    create_recommendation_csvs,
    summary_payload,
)
from src.common.paths import AIHUB_EXPORT_ROOT, AIHUB_SCRIPTS_ROOT


DEFAULT_INPUT = AIHUB_EXPORT_ROOT / "aihub_tourapi_place_mappings.csv"
DEFAULT_OUTPUT = AIHUB_EXPORT_ROOT / "aihub_tour_recommendation_places.csv"
DEFAULT_EXCLUDED_OUTPUT = (
    AIHUB_EXPORT_ROOT / "aihub_tour_recommendation_excluded.csv"
)
DEFAULT_FRANCHISE_RULES = AIHUB_SCRIPTS_ROOT / "configs" / "franchise_brands.json"
DEFAULT_NON_TOURISM_RULES = (
    AIHUB_SCRIPTS_ROOT / "configs" / "non_tourism_place_rules.json"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Deduplicate AIHub places and remove transport facilities and configured "
            "food, cafe, and convenience-store franchises."
        )
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--excluded-output",
        type=Path,
        default=DEFAULT_EXCLUDED_OUTPUT,
    )
    parser.add_argument(
        "--franchise-rules",
        type=Path,
        default=DEFAULT_FRANCHISE_RULES,
    )
    parser.add_argument(
        "--non-tourism-rules",
        type=Path,
        default=DEFAULT_NON_TOURISM_RULES,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = create_recommendation_csvs(
        args.input,
        args.output,
        args.excluded_output,
        args.franchise_rules,
        args.non_tourism_rules,
    )
    print(
        json.dumps(
            {
                "status": "filtered",
                **summary_payload(summary),
                "output": str(args.output.resolve()),
                "excluded_output": str(args.excluded_output.resolve()),
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
        print(f"AIHub recommendation CSV filtering failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
