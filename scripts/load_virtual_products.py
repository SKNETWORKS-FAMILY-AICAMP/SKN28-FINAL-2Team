"""Validate and upsert the curated virtual Jeju travel-product dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tour_recommender.storage.config import MySQLConfig
from tour_recommender.storage.mysql_repository import MySQLPlaceRepository


DEFAULT_INPUT = PROJECT_ROOT / "configs" / "virtual_travel_products.json"
DEFAULT_DETAILS = PROJECT_ROOT / "configs" / "virtual_travel_product_details.json"
DEFAULT_SCHEMA = PROJECT_ROOT / "sql" / "product_schema.sql"
VISIT_TIMES = ("09:30", "14:00", "17:00", "19:00")


def _validate(
    payload: dict[str, Any],
    details_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    products = payload.get("products")
    sources = payload.get("sources")
    if not isinstance(products, list) or len(products) != 30:
        raise ValueError("the virtual product dataset must contain exactly 30 products")
    if not isinstance(sources, dict) or not sources:
        raise ValueError("at least one official source reference is required")
    details = details_payload.get("products")
    if not isinstance(details, dict) or len(details) != 30:
        raise ValueError("the detail dataset must contain exactly 30 products")

    ids: set[str] = set()
    patterns: set[str] = set()
    required = {
        "id",
        "name",
        "summary",
        "pattern_code",
        "duration_days",
        "min_people",
        "max_people",
        "price_per_person",
        "regions",
        "tags",
        "companion_types",
        "transport_mode",
        "accommodation_type",
        "meal_count",
        "included",
        "excluded",
        "highlights",
        "source_keys",
    }
    normalized: list[dict[str, Any]] = []
    for index, product in enumerate(products, start=1):
        missing = sorted(required - set(product))
        if missing:
            raise ValueError(f"product {index} is missing fields: {', '.join(missing)}")
        product_id = str(product["id"])
        pattern = str(product["pattern_code"])
        if product_id in ids or pattern in patterns:
            raise ValueError(f"duplicate product id or pattern: {product_id}/{pattern}")
        ids.add(product_id)
        patterns.add(pattern)
        detail = details.get(product_id)
        if not isinstance(detail, dict):
            raise ValueError(f"missing product details: {product_id}")
        content_description = str(detail.get("content_description") or "").strip()
        itinerary = detail.get("itinerary")
        if len(content_description) < 40:
            raise ValueError(f"content_description is too short: {product_id}")
        if not isinstance(itinerary, list) or len(itinerary) != int(product["duration_days"]):
            raise ValueError(f"itinerary day count mismatch: {product_id}")
        expected_days = list(range(1, int(product["duration_days"]) + 1))
        actual_days = [day.get("day") for day in itinerary if isinstance(day, dict)]
        if actual_days != expected_days:
            raise ValueError(f"itinerary day sequence mismatch: {product_id}")
        visit_places: list[str] = []
        normalized_itinerary: list[dict[str, Any]] = []
        for day in itinerary:
            visits = day.get("visits")
            if not isinstance(visits, list) or len(visits) < 2:
                raise ValueError(f"at least two visits are required per day: {product_id}")
            normalized_visits: list[dict[str, str]] = []
            for visit_index, visit in enumerate(visits):
                if not isinstance(visit, list) or len(visit) != 2:
                    raise ValueError(f"invalid itinerary visit: {product_id}")
                place = str(visit[0]).strip()
                activity = str(visit[1]).strip()
                if not place or not activity:
                    raise ValueError(f"invalid itinerary visit: {product_id}")
                normalized_visits.append(
                    {
                        "time": VISIT_TIMES[min(visit_index, len(VISIT_TIMES) - 1)],
                        "place": place,
                        "activity": activity,
                    }
                )
                if place not in visit_places:
                    visit_places.append(place)
            normalized_itinerary.append(
                {
                    "day": day["day"],
                    "title": str(day.get("title") or f"Day {day['day']}").strip(),
                    "visits": normalized_visits,
                }
            )
        references = []
        for source_key in product["source_keys"]:
            if source_key not in sources:
                raise ValueError(f"unknown source key: {source_key}")
            references.append(sources[source_key])
        normalized.append(
            {
                **product,
                "content_description": content_description,
                "itinerary": normalized_itinerary,
                "visit_places": visit_places,
                "source_references": references,
            }
        )
    return normalized


def _load(products: list[dict[str, Any]], payload: dict[str, Any]) -> int:
    repository = MySQLPlaceRepository(MySQLConfig.from_env())
    repository.apply_schema(DEFAULT_SCHEMA)
    sql = """
        INSERT INTO virtual_travel_products (
            product_id, name, summary, content_description, pattern_code, duration_days,
            min_people, max_people, price_per_person, regions, tags,
            companion_types, transport_mode, accommodation_type, meal_count,
            included, excluded, highlights, itinerary, visit_places,
            source_references, is_virtual,
            availability, researched_at, data_version
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, TRUE, TRUE, %s, %s
        ) AS new
        ON DUPLICATE KEY UPDATE
            name = new.name, summary = new.summary,
            content_description = new.content_description,
            pattern_code = new.pattern_code, duration_days = new.duration_days,
            min_people = new.min_people, max_people = new.max_people,
            price_per_person = new.price_per_person, regions = new.regions,
            tags = new.tags, companion_types = new.companion_types,
            transport_mode = new.transport_mode,
            accommodation_type = new.accommodation_type,
            meal_count = new.meal_count, included = new.included,
            excluded = new.excluded, highlights = new.highlights,
            itinerary = new.itinerary, visit_places = new.visit_places,
            source_references = new.source_references, is_virtual = TRUE,
            availability = TRUE, researched_at = new.researched_at,
            data_version = new.data_version
    """
    rows = [
        (
            product["id"],
            product["name"],
            product["summary"],
            product["content_description"],
            product["pattern_code"],
            int(product["duration_days"]),
            int(product["min_people"]),
            int(product["max_people"]),
            int(product["price_per_person"]),
            json.dumps(product["regions"], ensure_ascii=False),
            json.dumps(product["tags"], ensure_ascii=False),
            json.dumps(product["companion_types"], ensure_ascii=False),
            product["transport_mode"],
            product["accommodation_type"],
            int(product["meal_count"]),
            json.dumps(product["included"], ensure_ascii=False),
            json.dumps(product["excluded"], ensure_ascii=False),
            json.dumps(product["highlights"], ensure_ascii=False),
            json.dumps(product["itinerary"], ensure_ascii=False),
            json.dumps(product["visit_places"], ensure_ascii=False),
            json.dumps(product["source_references"], ensure_ascii=False),
            payload["researched_at"],
            payload["version"],
        )
        for product in products
    ]
    with repository.connect() as connection:
        cursor = connection.cursor()
        try:
            cursor.execute("SHOW COLUMNS FROM virtual_travel_products")
            columns = {row[0] for row in cursor.fetchall()}
            migrations = {
                "content_description": "ALTER TABLE virtual_travel_products ADD COLUMN content_description TEXT NULL AFTER summary",
                "itinerary": "ALTER TABLE virtual_travel_products ADD COLUMN itinerary JSON NULL AFTER highlights",
                "visit_places": "ALTER TABLE virtual_travel_products ADD COLUMN visit_places JSON NULL AFTER itinerary",
            }
            migrated = False
            for column, statement in migrations.items():
                if column not in columns:
                    cursor.execute(statement)
                    migrated = True
            cursor.executemany(sql, rows)
            if migrated:
                cursor.execute(
                    "ALTER TABLE virtual_travel_products "
                    "MODIFY content_description TEXT NOT NULL, "
                    "MODIFY itinerary JSON NOT NULL, "
                    "MODIFY visit_places JSON NOT NULL"
                )
            placeholders = ",".join(["%s"] * len(products))
            cursor.execute(
                f"DELETE FROM virtual_travel_products WHERE product_id NOT IN ({placeholders})",
                [product["id"] for product in products],
            )
            connection.commit()
            cursor.execute("SELECT COUNT(*) FROM virtual_travel_products")
            return int(cursor.fetchone()[0])
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--details", type=Path, default=DEFAULT_DETAILS)
    args = parser.parse_args()
    load_dotenv(PROJECT_ROOT / ".env")
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    details_payload = json.loads(args.details.read_text(encoding="utf-8"))
    products = _validate(payload, details_payload)
    count = _load(products, payload)
    print(
        json.dumps(
            {
                "version": payload["version"],
                "validated": len(products),
                "stored": count,
                "itinerary_days": sum(len(product["itinerary"]) for product in products),
                "unique_visit_places": len(
                    {
                        place
                        for product in products
                        for place in product["visit_places"]
                    }
                ),
            },
            ensure_ascii=False,
        )
    )
    return 0 if count == 30 else 1


if __name__ == "__main__":
    raise SystemExit(main())
