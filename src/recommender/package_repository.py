from __future__ import annotations

from typing import Any, Protocol, Sequence

from src.config.settings import MySQLConfig
from src.storage.mysql_repository import MySQLPlaceRepository

from .models import PackageCandidate, PackageItem
from .profile_mapping import parse_csv_values


class PackageRepository(Protocol):
    def find_active_by_duration(
        self,
        duration_days: int,
    ) -> list[PackageCandidate]:
        ...

    def get_places(
        self,
        content_ids: Sequence[int],
    ) -> dict[int, dict[str, Any]]:
        ...


class MySQLPackageRepository:
    def __init__(self, config: MySQLConfig) -> None:
        self._places = MySQLPlaceRepository(config)

    def find_active_by_duration(
        self,
        duration_days: int,
    ) -> list[PackageCandidate]:
        if duration_days not in range(1, 6):
            raise ValueError(
                "duration_days must be between 1 and 5"
            )

        with self._places.connect() as connection:
            cursor = connection.cursor(dictionary=True)

            try:
                cursor.execute(
                    _PACKAGE_SELECT,
                    (duration_days,),
                )

                rows = [
                    dict(row)
                    for row in cursor.fetchall()
                ]

            finally:
                cursor.close()

        return _group_packages(rows)

    def get_places(
        self,
        content_ids: Sequence[int],
    ) -> dict[int, dict[str, Any]]:
        return {
            int(row["content_id"]): row
            for row in self._places.get_places_by_ids(
                content_ids
            )
        }


def _group_packages(
    rows: list[dict[str, Any]],
) -> list[PackageCandidate]:
    grouped: dict[int, dict[str, Any]] = {}

    for row in rows:
        database_id = int(row["package_db_id"])

        entry = grouped.setdefault(
            database_id,
            {
                "row": row,
                "items": [],
            },
        )

        if row.get("item_id") is not None:
            item_categories = _normalize_string_tuple(
                row.get("item_tags")
            )

            entry["items"].append(
                PackageItem(
                    day=_optional_int(row.get("day_no")),
                    sequence=_optional_int(row.get("sequence")),
                    item_type=str(row["item_type"]),
                    content_id=int(row["content_id"]),
                    place_categories=parse_csv_values(row.get("item_tags")),
                    title=str(row.get("place_title") or ""),
                    stay_minutes=_optional_int(row.get("stay_minutes")),
                    longitude=_optional_float(row.get("longitude")),
                    latitude=_optional_float(row.get("latitude")),
                )
            )

    candidates: list[PackageCandidate] = []
    for database_id, entry in grouped.items():
        row = entry["row"]
        candidates.append(
            PackageCandidate(
                package_id=str(row["package_id"]),
                title=str(row["title"]),
                summary=str(row.get("summary") or ""),
                region=str(row["region"]),
                duration_days=int(row["duration_days"]),
                estimated_price=int(row["estimated_price"]),
                companion_types=parse_csv_values(row.get("companion")),
                place_categories=_package_categories(
                    parse_csv_values(row.get("tags")), entry["items"]
                ),
                items=tuple(entry["items"]),
                database_id=database_id,
            )
        )

    return candidates


def _optional_int(
    value: Any,
) -> int | None:
    if value is None:
        return None

    return int(value)


def _optional_float(
    value: Any,
) -> float | None:
    if value is None:
        return None

    return float(value)


def _normalize_string_tuple(
    value: Any,
) -> tuple[str, ...]:
    if value is None:
        return ()

    if isinstance(value, str):
        value = value.strip()

        if not value:
            return ()

        try:
            parsed = json.loads(value)

            if isinstance(parsed, list):
                return tuple(
                    str(item).strip()
                    for item in parsed
                    if str(item).strip()
                )

            if isinstance(parsed, str):
                parsed = parsed.strip()

                if parsed:
                    return (parsed,)

        except json.JSONDecodeError:
            pass

        if "," in value:
            return tuple(
                item.strip()
                for item in value.split(",")
                if item.strip()
            )

        return (value,)

    if isinstance(
        value,
        (list, tuple, set),
    ):
        return tuple(
            str(item).strip()
            for item in value
            if str(item).strip()
        )

    return (str(value).strip(),)


def _deserialize_match_profile(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError("travel_packages.match_profile must be a JSON object")
    return value


def _package_categories(
    package_tags: tuple[str, ...], items: list[PackageItem]
) -> tuple[str, ...]:
    values = set(package_tags)
    for item in items:
        values.update(item.place_categories)
    return tuple(sorted(values))


_PACKAGE_SELECT = """
SELECT
    tp.id AS package_db_id,
    tp.package_id,
    tp.title,
    tp.summary,
    tp.region,
    tp.duration_days,
    tp.estimated_price,
    tp.companion,
    tp.tags,
    pi.id AS item_id,
    pi.day_no,
    pi.sequence,
    pi.item_type,
    pi.content_id,
    pi.tags AS item_tags,
    pi.stay_minutes,
    pi.tags AS item_tags,
    p.title AS place_title,
    p.longitude,
    p.latitude
FROM travel_packages AS tp
LEFT JOIN package_items AS pi
    ON pi.package_db_id = tp.id
LEFT JOIN places AS p
    ON p.content_id = pi.content_id
WHERE
    tp.is_active = TRUE
    AND tp.duration_days = %s
ORDER BY
    tp.id,
    pi.day_no,
    pi.sequence,
    pi.id
"""
