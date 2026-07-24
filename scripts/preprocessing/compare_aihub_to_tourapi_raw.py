"""Write one CSV comparing AIHub recommendation places with TourAPI raw data."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from src.aihub.recommendation_csv import (
    read_mapping_csv,
    write_csv_atomic,
)
from src.aihub.tourapi_raw_comparison import (
    CLASSIFICATION_COLUMNS,
    classify_tourapi_against_aihub,
    load_tourapi_raw_places,
)
from src.common.paths import AIHUB_EXPORT_ROOT, TOURAPI_DATA_ROOT


DEFAULT_INPUT = AIHUB_EXPORT_ROOT / "aihub_tour_recommendation_places.csv"
DEFAULT_TOURAPI_RAW = (
    TOURAPI_DATA_ROOT
    / "raw"
    / "korea_tour_openapi_jeju_places.csv"
)
DEFAULT_OUTPUT = AIHUB_EXPORT_ROOT / "aihub_tourapi_raw_comparison.csv"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Classify each TourAPI raw place by its relationship to AIHub."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--tourapi-raw", type=Path, default=DEFAULT_TOURAPI_RAW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows = read_mapping_csv(args.input)
    raw_columns, tourapi_places = load_tourapi_raw_places(args.tourapi_raw)
    classified, summary = classify_tourapi_against_aihub(tourapi_places, rows)
    write_csv_atomic(
        args.output,
        (*raw_columns, *CLASSIFICATION_COLUMNS),
        classified,
    )
    print(
        json.dumps(
            {
                "status": "compared",
                **asdict(summary),
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
        print(f"AIHub/TourAPI raw comparison failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
