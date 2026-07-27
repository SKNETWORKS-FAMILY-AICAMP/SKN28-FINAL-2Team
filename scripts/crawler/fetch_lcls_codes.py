from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys
from typing import Sequence

from src.common.paths import REPOSITORY_ROOT, TOURAPI_DATA_ROOT
from src.tourapi.crawler.export import write_json, write_records_csv
from src.tourapi.crawler.lcls import (
    LclsCodeResult,
    fetch_lcls_code_tree,
)
from src.tourapi.crawler.openapi_client import (
    DEFAULT_OPENAPI_CALL_BUDGET,
    DEFAULT_OPENAPI_MOBILE_APP,
    DEFAULT_OPENAPI_MOBILE_OS,
    DEFAULT_OPENAPI_PAGE_SIZE,
    OpenApiError,
)
from src.common.env import load_env_file


DEFAULT_OUTPUT_DIR = TOURAPI_DATA_ROOT / "raw"
OUTPUT_STEM = "korea_tour_openapi_lcls_codes"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch official TourAPI lclsSystm classification codes."
    )
    parser.add_argument("--service-key", help="TourAPI service key. Prefer .env or env vars.")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=REPOSITORY_ROOT / ".env",
        help="Optional .env file with KOREA_TOUR_API_KEY or DATA_GO_KR_SERVICE_KEY.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--mobile-os", default=DEFAULT_OPENAPI_MOBILE_OS)
    parser.add_argument("--mobile-app", default=DEFAULT_OPENAPI_MOBILE_APP)
    parser.add_argument("--page-size", type=int, default=DEFAULT_OPENAPI_PAGE_SIZE)
    parser.add_argument(
        "--depth",
        type=int,
        choices=[1, 2, 3],
        default=3,
        help="1: lclsSystm1 only, 2: include lclsSystm2, 3: include lclsSystm3.",
    )
    parser.add_argument("--call-budget", type=int, default=DEFAULT_OPENAPI_CALL_BUDGET)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Also write a JSON copy. CSV is the canonical database input.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    load_env_file(args.env_file)

    try:
        result = fetch_lcls_code_tree(
            service_key=args.service_key,
            mobile_os=args.mobile_os,
            mobile_app=args.mobile_app,
            page_size=args.page_size,
            max_depth=args.depth,
            call_budget=args.call_budget,
            timeout=args.timeout,
            retries=args.retries,
        )
    except (ValueError, OpenApiError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    _write_outputs(result, args.output_dir, write_json_output=args.json)
    _print_summary(result, args.call_budget)
    return 0


def _write_outputs(
    result: LclsCodeResult,
    output_dir: Path,
    *,
    write_json_output: bool,
) -> None:
    csv_output = output_dir / f"{OUTPUT_STEM}.csv"
    json_output = output_dir / f"{OUTPUT_STEM}.json"
    write_records_csv(result.records, csv_output)
    if write_json_output:
        write_json(
            {
                "max_depth": result.max_depth,
                "calls_used": result.calls_used,
                "count": len(result.records),
                "records": result.records,
            },
            json_output,
        )


def _print_summary(result: LclsCodeResult, call_budget: int) -> None:
    counts_by_depth = Counter(str(record.get("_query_depth", "")) for record in result.records)
    print(f"Saved {len(result.records)} lcls code rows.")
    print(f"Calls used: {result.calls_used}/{call_budget}")
    for depth in sorted(counts_by_depth, key=int):
        print(f"Depth {depth}: {counts_by_depth[depth]} rows")


if __name__ == "__main__":
    raise SystemExit(main())
