from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from src.common.paths import TOURAPI_DATA_ROOT, TOURAPI_SCRIPTS_ROOT
from src.tourapi.preprocessing.preprocessing import (
    build_place_vector_payload,
    load_place_rules,
    preprocess_place_csv,
    write_place_vector_payload,
)


DEFAULT_INPUT = TOURAPI_DATA_ROOT / "raw" / "korea_tour_openapi_jeju_places.csv"
DEFAULT_OUTPUT = TOURAPI_DATA_ROOT / "processed" / "jeju_place_rag_documents.json"
DEFAULT_RULES = TOURAPI_SCRIPTS_ROOT / "configs" / "place_rules.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preprocess the unified Jeju place CSV into RAG-ready JSON."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    args = parser.parse_args()

    try:
        rules = load_place_rules(args.rules)
        result = preprocess_place_csv(args.input, rules)
        payload = build_place_vector_payload(result, source_file=args.input.name)
        write_place_vector_payload(payload, args.output)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Saved {len(result.documents)} RAG documents to {args.output}")
    print(f"Source records: {result.source_record_count}")
    print(f"Excluded records: {result.excluded_count}")
    print(f"Datasets: {result.dataset_counts}")
    print(f"Collections: {result.collection_counts}")
    print(f"Recommendation scopes: {result.scope_counts}")
    print(f"Place subtypes: {result.subtype_counts}")
    print(f"Itinerary roles: {result.itinerary_role_counts}")
    print(f"Route-ineligible documents: {result.route_ineligible_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
