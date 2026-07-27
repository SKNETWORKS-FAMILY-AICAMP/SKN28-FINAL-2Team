from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from src.common.paths import (
    REPOSITORY_ROOT,
    TOURAPI_DATA_ROOT,
    TOURAPI_SCRIPTS_ROOT,
)
from src.tourapi.crawler.openapi_client import (
    DEFAULT_OPENAPI_CALL_BUDGET,
    DEFAULT_OPENAPI_MOBILE_APP,
    DEFAULT_OPENAPI_MOBILE_OS,
    OpenApiError,
    resolve_service_key,
)
from src.tourapi.crawler.collection import (
    CollectionStatus,
    collection_status,
    initialize_place_rows,
    write_place_csv,
)
from src.tourapi.crawler.pipeline import (
    CollectionOptions,
    TourApiCollectionPipeline,
)
from src.tourapi.preprocessing.preprocessing import (
    build_place_vector_payload,
    load_place_rules,
    preprocess_place_csv,
    write_place_vector_payload,
)
from src.common.env import load_env_file


DEFAULT_TOURISM_SOURCE = (
    TOURAPI_DATA_ROOT
    / "raw"
    / "korea_tour_openapi_jeju_lcls_address_tourism.csv"
)
DEFAULT_RAW_OUTPUT = (
    TOURAPI_DATA_ROOT / "raw" / "korea_tour_openapi_jeju_places.csv"
)
DEFAULT_RAG_OUTPUT = (
    TOURAPI_DATA_ROOT / "processed" / "jeju_place_rag_documents.json"
)
DEFAULT_RULES = TOURAPI_SCRIPTS_ROOT / "configs" / "place_rules.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Collect unified Jeju tourism, lodging, food, leisure, and shopping "
            "records with resumable TourAPI checkpoints."
        )
    )
    parser.add_argument("--service-key", help="TourAPI service key. Prefer .env.")
    parser.add_argument("--env-file", type=Path, default=REPOSITORY_ROOT / ".env")
    parser.add_argument("--tourism-source", type=Path, default=DEFAULT_TOURISM_SOURCE)
    parser.add_argument("--raw-output", type=Path, default=DEFAULT_RAW_OUTPUT)
    parser.add_argument("--rag-output", type=Path, default=DEFAULT_RAG_OUTPUT)
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    parser.add_argument(
        "--call-budget",
        type=int,
        default=DEFAULT_OPENAPI_CALL_BUDGET,
        help="Remaining TourAPI calls available today. Default: 1000.",
    )
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--checkpoint-every", type=int, default=25)
    parser.add_argument("--mobile-os", default=DEFAULT_OPENAPI_MOBILE_OS)
    parser.add_argument("--mobile-app", default=DEFAULT_OPENAPI_MOBILE_APP)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Show local progress without calling TourAPI or changing files.",
    )
    args = parser.parse_args()

    if args.call_budget < 1 or args.page_size < 1 or args.checkpoint_every < 1:
        print(
            "Error: --call-budget, --page-size, and --checkpoint-every must be at least 1",
            file=sys.stderr,
        )
        return 1

    try:
        rules = load_place_rules(args.rules)
        rows = initialize_place_rows(
            args.raw_output,
            args.tourism_source,
            rules,
        )
        status = collection_status(rows)
        _print_status(status, heading="Local collection plan")
        if args.plan_only:
            return 0

        load_env_file(args.env_file)
        service_key = resolve_service_key(args.service_key)
        write_place_csv(rows, args.raw_output)

        pipeline = TourApiCollectionPipeline(
            CollectionOptions(
                output_path=args.raw_output,
                service_key=service_key,
                call_budget=args.call_budget,
                page_size=args.page_size,
                checkpoint_every=args.checkpoint_every,
                mobile_os=args.mobile_os,
                mobile_app=args.mobile_app,
                timeout=args.timeout,
                retries=args.retries,
            ),
            on_message=print,
            on_detail_progress=_print_detail_progress,
        )
        pipeline_result = pipeline.run(rows, rules)
        calls_used = pipeline_result.calls_used
        status = pipeline_result.status

        if not pipeline_result.complete:
            _print_incomplete(status, calls_used, args.call_budget)
            return 0

        result = preprocess_place_csv(args.raw_output, rules)
        payload = build_place_vector_payload(result, source_file=args.raw_output.name)
        write_place_vector_payload(payload, args.rag_output)
        print(f"Saved {len(result.documents)} RAG documents to {args.rag_output}")
        print(f"TourAPI calls used this run: {calls_used}/{args.call_budget}")
        _print_status(status, heading="Collection complete")
    except OpenApiError as exc:
        if _is_quota_exceeded(exc):
            print("TourAPI daily quota reached. The latest checkpoint was saved.")
            print("Run the same command again after the daily quota resets.")
            return 0
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


def _print_status(status: CollectionStatus, *, heading: str) -> None:
    print(heading)
    print(f"  rows: {status.row_count}")
    print(f"  datasets: {status.dataset_counts}")
    print(f"  missing datasets: {list(status.missing_datasets)}")
    print(f"  common detail pending: {status.common_pending}")
    print(f"  intro detail pending: {status.intro_pending}")


def _print_incomplete(
    status: CollectionStatus, calls_used: int, call_budget: int
) -> None:
    print(f"TourAPI calls used this run: {calls_used}/{call_budget}")
    _print_status(status, heading="Collection checkpoint saved")
    print("Run the same command again when the daily quota is available.")


def _print_detail_progress(detail_kind: str, completed: int, total: int) -> None:
    print(f"[{detail_kind}] checkpoint: {completed}/{total}")


def _is_quota_exceeded(error: OpenApiError) -> bool:
    message = str(error).lower()
    return "429" in message or "quota exceeded" in message


if __name__ == "__main__":
    raise SystemExit(main())
