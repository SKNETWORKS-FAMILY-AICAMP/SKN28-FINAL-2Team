"""Build privacy-conscious AIHub trip RAG documents from the MySQL source tables."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tour_recommender.aihub.rag_documents import build_aihub_rag_payload
from tour_recommender.aihub.storage import connect_mysql, mysql_config_from_env
from tour_recommender.utils.config import load_env_file


DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "aihub_rag_documents.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-visits-per-trip", type=int, default=70)
    args = parser.parse_args()

    load_env_file(PROJECT_ROOT / ".env")
    connection = connect_mysql(mysql_config_from_env())
    try:
        payload = build_aihub_rag_payload(
            connection,
            max_visits_per_trip=args.max_visits_per_trip,
        )
    finally:
        connection.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary_output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    temporary_output.replace(args.output)
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                **payload["statistics"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
