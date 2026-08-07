"""Recommend stored travel packages for an itinerary RAG JSON response."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.common.env import load_env_file
from src.config.settings import MySQLConfig
from src.recommender import (
    MySQLPackageRepository,
    PackageRecommendationService,
)
from src.recommender.models import PackageCandidate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--input", type=Path)
    input_group.add_argument(
        "--smoke-test",
        action="store_true",
        help="build a safe test itinerary from one stored package",
    )
    parser.add_argument("--env-file", type=Path, default=PROJECT_ROOT / ".env")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument(
        "--smoke-duration",
        type=int,
        default=1,
        choices=range(1, 6),
        metavar="1-5",
    )
    args = parser.parse_args()

    load_env_file(args.env_file)
    admin_aliases = {
        "MYSQL_HOST": "MYSQL_ADMIN_HOST",
        "MYSQL_PORT": "MYSQL_ADMIN_PORT",
        "MYSQL_USER": "MYSQL_ADMIN_USER",
        "MYSQL_PASSWORD": "MYSQL_ADMIN_PASSWORD",
    }
    for standard_name, admin_name in admin_aliases.items():
        if not os.environ.get(standard_name) and os.environ.get(admin_name):
            os.environ[standard_name] = os.environ[admin_name]
    if not os.environ.get("MYSQL_DATABASE") and os.environ.get("TRAVEL_DB_NAME"):
        os.environ["MYSQL_DATABASE"] = os.environ["TRAVEL_DB_NAME"]
    repository = MySQLPackageRepository(MySQLConfig.from_env())
    service = PackageRecommendationService(repository)
    if args.smoke_test:
        candidates = repository.find_active_by_duration(args.smoke_duration)
        if not candidates:
            raise ValueError(
                f"no active package for smoke duration: {args.smoke_duration}"
            )
        payload = _build_smoke_payload(candidates[0])
    else:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
    result = service.recommend(payload, top_k=args.top_k)
    result["meta"]["input_source"] = (
        "db_smoke_test" if args.smoke_test else str(args.input)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _build_smoke_payload(package: PackageCandidate) -> dict[str, object]:
    conditions = {
        "duration_days": package.duration_days,
        "party_type": package.companion_types[0] if package.companion_types else "solo",
        "preferred_visit_types": [
            package.place_categories[0] if package.place_categories else "nature"
        ],
    }
    days = []
    for day in range(1, package.duration_days + 1):
        items = [
            item
            for item in package.tourism_items
            if item.day == day
        ]
        days.append(
            {
                "day": day,
                "stops": [
                    {
                        "sequence": index,
                        "role": "visit",
                        "content_id": item.content_id,
                        "title": item.title,
                    }
                    for index, item in enumerate(items, start=1)
                ],
            }
        )
    return {"condition": conditions, "itinerary": {"days": days}}


if __name__ == "__main__":
    raise SystemExit(main())
