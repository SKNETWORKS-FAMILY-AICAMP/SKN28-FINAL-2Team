"""Validate and upsert generated Jeju packages into MySQL."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import MySQLConfig
from src.storage.mysql_repository import MySQLPlaceRepository


DEFAULT_INPUT = PROJECT_ROOT / "data" / "package_evaluation" / "final_packages.30.json"
DEFAULT_SCHEMA = PROJECT_ROOT / "src" / "storage" / "sql" / "package_schema.sql"


def _collect_items(package: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for day in package["days"]:
        day_no = int(day["day"])
        restaurant = day.get("restaurant")
        after_order = None
        if restaurant:
            after_order = int(
                restaurant.get(
                    "recommended_after_place_order",
                    len(day["places"]),
                )
            )

        sequence = 0
        restaurant_added = False
        for place in sorted(day["places"], key=lambda row: int(row["order"])):
            sequence += 1
            items.append(
                {
                    "day_no": day_no,
                    "sequence": sequence,
                    "item_type": "tourism",
                    "content_id": int(place["content_id"]),
                    "stay_minutes": int(place["stay_minutes"]),
                }
            )
            if restaurant and int(place["order"]) == after_order:
                sequence += 1
                items.append(
                    {
                        "day_no": day_no,
                        "sequence": sequence,
                        "item_type": "restaurant",
                        "content_id": int(restaurant["content_id"]),
                        "stay_minutes": int(restaurant.get("stay_minutes", 60)),
                    }
                )
                restaurant_added = True

        if restaurant and not restaurant_added:
            sequence += 1
            items.append(
                {
                    "day_no": day_no,
                    "sequence": sequence,
                    "item_type": "restaurant",
                    "content_id": int(restaurant["content_id"]),
                    "stay_minutes": int(restaurant.get("stay_minutes", 60)),
                }
            )

    hotel = package.get("hotel")
    if hotel:
        items.append(
            {
                "day_no": None,
                "sequence": None,
                "item_type": "hotel",
                "content_id": int(hotel["content_id"]),
                "stay_minutes": None,
            }
        )
    return items


def _validate(
    payload: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    packages = payload.get("packages")
    if not isinstance(packages, list) or not packages:
        raise ValueError("packages must be a non-empty list")

    seen_package_ids: set[str] = set()
    normalized_items: list[dict[str, Any]] = []
    for package in packages:
        package_id = str(package["package_id"])
        if package_id in seen_package_ids:
            raise ValueError(f"duplicate package_id: {package_id}")
        seen_package_ids.add(package_id)

        duration = int(package["duration_days"])
        if duration not in range(1, 6):
            raise ValueError(f"duration_days must be 1-5: {package_id}")
        if len(package["days"]) != duration:
            raise ValueError(f"day count mismatch: {package_id}")
        if int(package["estimated_price"]) < 0:
            raise ValueError(f"estimated_price must not be negative: {package_id}")
        if not isinstance(package.get("match_profile"), dict):
            raise ValueError(f"match_profile must be an object: {package_id}")

        expected_days = list(range(1, duration + 1))
        actual_days = [int(day["day"]) for day in package["days"]]
        if actual_days != expected_days:
            raise ValueError(f"day sequence mismatch: {package_id}")

        for day in package["days"]:
            place_count = len(day.get("places", []))
            if not 3 <= place_count <= 4:
                raise ValueError(
                    f"tourism place count must be 3-4: "
                    f"{package_id}, day {day['day']}"
                )
            if not day.get("restaurant"):
                raise ValueError(
                    f"restaurant missing: {package_id}, day {day['day']}"
                )

        has_hotel = bool(package.get("hotel"))
        if duration == 1 and has_hotel:
            raise ValueError(f"day trip must not have a hotel: {package_id}")
        if duration > 1 and not has_hotel:
            raise ValueError(f"overnight package needs a hotel: {package_id}")

        normalized_items.extend(
            {"package_id": package_id, **item}
            for item in _collect_items(package)
        )

    return packages, normalized_items


def _validate_tourapi_links(cursor: Any, items: list[dict[str, Any]]) -> None:
    content_ids = sorted({int(item["content_id"]) for item in items})
    placeholders = ",".join(["%s"] * len(content_ids))
    cursor.execute(
        "SELECT content_id, content_type_id FROM places "
        f"WHERE content_id IN ({placeholders})",
        content_ids,
    )
    found = {int(row[0]): int(row[1]) for row in cursor.fetchall()}
    missing = sorted(set(content_ids) - found.keys())
    if missing:
        raise ValueError(f"TourAPI places missing content_id values: {missing}")

    for item in items:
        content_type_id = found[int(item["content_id"])]
        if item["item_type"] == "restaurant" and content_type_id != 39:
            raise ValueError(
                "restaurant content type mismatch: "
                f"{item['content_id']} -> {content_type_id}"
            )
        if item["item_type"] == "hotel" and content_type_id != 32:
            raise ValueError(
                "hotel content type mismatch: "
                f"{item['content_id']} -> {content_type_id}"
            )


def _load(
    packages: list[dict[str, Any]],
    items: list[dict[str, Any]],
    schema_version: str,
    env_file: Path,
) -> dict[str, Any]:
    repository = MySQLPlaceRepository(MySQLConfig.from_env(env_file))
    repository.apply_schema(DEFAULT_SCHEMA)

    package_sql = """
        INSERT INTO travel_packages (
            package_id, title, summary, region, duration_days,
            estimated_price, match_profile, schema_version, is_active
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE) AS new
        ON DUPLICATE KEY UPDATE
            title = new.title,
            summary = new.summary,
            region = new.region,
            duration_days = new.duration_days,
            estimated_price = new.estimated_price,
            match_profile = new.match_profile,
            schema_version = new.schema_version,
            is_active = TRUE
    """
    package_rows = [
        (
            package["package_id"],
            package["title"],
            package.get("summary", ""),
            package["region"],
            int(package["duration_days"]),
            int(package["estimated_price"]),
            json.dumps(package["match_profile"], ensure_ascii=False),
            schema_version,
        )
        for package in packages
    ]
    package_ids = [str(package["package_id"]) for package in packages]
    placeholders = ",".join(["%s"] * len(package_ids))

    with repository.connect() as connection:
        cursor = connection.cursor()
        try:
            _validate_tourapi_links(cursor, items)
            cursor.execute(
                "DELETE pi FROM package_items pi "
                "JOIN travel_packages tp ON tp.id = pi.package_db_id "
                f"WHERE tp.package_id IN ({placeholders})",
                package_ids,
            )
            cursor.executemany(package_sql, package_rows)

            cursor.execute(
                "SELECT id, package_id FROM travel_packages "
                f"WHERE package_id IN ({placeholders})",
                package_ids,
            )
            database_ids = {str(row[1]): int(row[0]) for row in cursor.fetchall()}
            item_rows = [
                (
                    database_ids[item["package_id"]],
                    item["day_no"],
                    item["sequence"],
                    item["item_type"],
                    item["content_id"],
                    item["stay_minutes"],
                )
                for item in items
            ]
            cursor.executemany(
                "INSERT INTO package_items "
                "(package_db_id, day_no, sequence, item_type, content_id, "
                "stay_minutes) VALUES (%s, %s, %s, %s, %s, %s)",
                item_rows,
            )
            connection.commit()

            cursor.execute(
                "SELECT COUNT(*) FROM travel_packages "
                f"WHERE package_id IN ({placeholders})",
                package_ids,
            )
            stored_packages = int(cursor.fetchone()[0])
            cursor.execute(
                "SELECT pi.item_type, COUNT(*) FROM package_items pi "
                "JOIN travel_packages tp ON tp.id = pi.package_db_id "
                f"WHERE tp.package_id IN ({placeholders}) "
                "GROUP BY pi.item_type ORDER BY pi.item_type",
                package_ids,
            )
            stored_items = {str(row[0]): int(row[1]) for row in cursor.fetchall()}
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()

    return {"packages": stored_packages, "items": stored_items}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--env-file", type=Path, default=PROJECT_ROOT / ".env")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    packages, items = _validate(payload)
    item_counts = dict(sorted(Counter(item["item_type"] for item in items).items()))

    result: dict[str, Any] = {
        "validated_packages": len(packages),
        "validated_items": item_counts,
        "unique_content_ids": len({item["content_id"] for item in items}),
    }
    if not args.validate_only:
        result["stored"] = _load(
            packages,
            items,
            str(payload.get("schema_version", "1.0")),
            args.env_file,
        )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
