"""Build recommendation candidates from AIHub place mapping rows."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
import math
import re
import unicodedata
from typing import Any, Mapping, Sequence

from .place_mapping import haversine_meters, normalize_address, normalize_name
from .row_values import (
    json_strings as _json_strings,
    optional_float as _optional_float,
    required_int as _required_int,
    stringify_row as _stringify_row,
)
from src.common.disjoint_set import DisjointSet


DEDUPLICATION_RADIUS_METERS = 75.0
_SPATIAL_BUCKET_DEGREES = 0.001
_STATUS_PRIORITY = {"MATCHED": 3, "REVIEW": 2, "UNMATCHED": 1}
_NON_ALPHANUMERIC = re.compile(r"[^0-9a-z가-힣]+")
_SHORT_ASCII_ALIAS = re.compile(r"^[a-z0-9]{1,3}$")

AUDIT_COLUMNS = (
    "merged_aihub_place_ids",
    "merged_aihub_place_count",
    "merged_mapping_conflict",
)


@dataclass(frozen=True)
class FranchiseBrand:
    name: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class FranchiseRules:
    applicable_visit_area_type_codes: frozenset[str]
    brands: tuple[FranchiseBrand, ...]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "FranchiseRules":
        raw_codes = payload.get("applicable_visit_area_type_codes")
        raw_brands = payload.get("brands")
        if not isinstance(raw_codes, list) or not raw_codes:
            raise ValueError("franchise rules require applicable visit area type codes")
        if not isinstance(raw_brands, list) or not raw_brands:
            raise ValueError("franchise rules require a non-empty brands list")

        brands: list[FranchiseBrand] = []
        seen_aliases: dict[str, str] = {}
        for item in raw_brands:
            if not isinstance(item, Mapping):
                raise ValueError("each franchise brand must be an object")
            name = str(item.get("name") or "").strip()
            raw_aliases = item.get("aliases")
            if not name or not isinstance(raw_aliases, list) or not raw_aliases:
                raise ValueError("each franchise brand requires name and aliases")
            aliases = tuple(str(alias).strip() for alias in raw_aliases if str(alias).strip())
            if not aliases:
                raise ValueError(f"franchise brand has no usable aliases: {name}")
            for alias in aliases:
                normalized = _normalize_franchise_text(alias)
                existing = seen_aliases.get(normalized)
                if existing is not None and existing != name:
                    raise ValueError(
                        f"franchise alias is assigned to multiple brands: {alias}"
                    )
                seen_aliases[normalized] = name
            brands.append(FranchiseBrand(name=name, aliases=aliases))

        return cls(
            applicable_visit_area_type_codes=frozenset(str(code) for code in raw_codes),
            brands=tuple(brands),
        )


@dataclass(frozen=True)
class NonTourismRules:
    transport_visit_area_type_codes: frozenset[str]
    name_keywords: tuple[str, ...]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "NonTourismRules":
        raw_codes = payload.get("transport_visit_area_type_codes")
        raw_keywords = payload.get("name_keywords")
        if not isinstance(raw_codes, list) or not raw_codes:
            raise ValueError("non-tourism rules require transport type codes")
        if not isinstance(raw_keywords, list):
            raise ValueError("non-tourism name keywords must be a list")
        keywords = tuple(
            str(keyword).strip() for keyword in raw_keywords if str(keyword).strip()
        )
        if len({_normalize_franchise_text(keyword) for keyword in keywords}) != len(
            keywords
        ):
            raise ValueError("non-tourism name keywords must be unique")
        return cls(
            transport_visit_area_type_codes=frozenset(str(code) for code in raw_codes),
            name_keywords=keywords,
        )


@dataclass(frozen=True)
class RecommendationFilterSummary:
    input_rows: int
    deduplicated_rows: int
    duplicate_rows_merged: int
    recommendation_rows: int
    excluded_rows: int
    transport_rows_removed: int
    non_tourism_keyword_rows_removed: int
    franchise_rows_removed: int


@dataclass(frozen=True)
class RecommendationFilterResult:
    recommendations: tuple[dict[str, str], ...]
    exclusions: tuple[dict[str, str], ...]
    summary: RecommendationFilterSummary


def build_recommendation_filter(
    rows: Sequence[Mapping[str, Any]],
    franchise_rules: FranchiseRules,
    non_tourism_rules: NonTourismRules,
    *,
    coordinate_radius_m: float = DEDUPLICATION_RADIUS_METERS,
) -> RecommendationFilterResult:
    """Deduplicate AIHub places, then remove transport and franchise rows."""

    deduplicated = deduplicate_aihub_rows(
        rows,
        coordinate_radius_m=coordinate_radius_m,
    )
    recommendations: list[dict[str, str]] = []
    exclusions: list[dict[str, str]] = []
    transport_removed = 0
    non_tourism_keyword_removed = 0
    franchise_removed = 0

    for row in deduplicated:
        reason: str | None = None
        type_code = str(row.get("aihub_visit_area_type_code") or "").strip()
        if type_code in non_tourism_rules.transport_visit_area_type_codes:
            reason = f"TRANSPORT_TYPE:{type_code}"
            transport_removed += 1
        else:
            keyword = detect_non_tourism_keyword(
                str(row.get("aihub_place_name") or ""),
                non_tourism_rules,
            )
            if keyword is not None:
                reason = f"NON_TOURISM_KEYWORD:{keyword}"
                non_tourism_keyword_removed += 1

        if reason is None and type_code in franchise_rules.applicable_visit_area_type_codes:
            franchise = detect_franchise(
                str(row.get("aihub_place_name") or ""),
                franchise_rules,
            )
            if franchise is not None:
                reason = f"FRANCHISE:{franchise}"
                franchise_removed += 1

        if reason is None:
            recommendations.append(dict(row))
        else:
            excluded = dict(row)
            excluded["exclusion_reason"] = reason
            exclusions.append(excluded)

    recommendations.sort(key=_output_sort_key)
    exclusions.sort(key=_output_sort_key)
    return RecommendationFilterResult(
        recommendations=tuple(recommendations),
        exclusions=tuple(exclusions),
        summary=RecommendationFilterSummary(
            input_rows=len(rows),
            deduplicated_rows=len(deduplicated),
            duplicate_rows_merged=len(rows) - len(deduplicated),
            recommendation_rows=len(recommendations),
            excluded_rows=len(exclusions),
            transport_rows_removed=transport_removed,
            non_tourism_keyword_rows_removed=non_tourism_keyword_removed,
            franchise_rows_removed=franchise_removed,
        ),
    )


def deduplicate_aihub_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    coordinate_radius_m: float = DEDUPLICATION_RADIUS_METERS,
) -> list[dict[str, str]]:
    """Merge only AIHub rows supported by name, address, POI, or proximity."""

    if coordinate_radius_m <= 0:
        raise ValueError("coordinate_radius_m must be greater than zero")
    materialized = [_stringify_row(row) for row in rows]
    union_find = DisjointSet(len(materialized))
    names = [normalize_name(row.get("aihub_place_name")) for row in materialized]
    addresses = [
        normalize_address(row.get("aihub_road_address"))
        or normalize_address(row.get("aihub_lot_address"))
        for row in materialized
    ]
    coordinates = [
        (
            _optional_float(row.get("aihub_longitude")),
            _optional_float(row.get("aihub_latitude")),
        )
        for row in materialized
    ]

    by_name_address: dict[tuple[str, str], int] = {}
    for index, (name, address) in enumerate(zip(names, addresses)):
        if not name or not address:
            continue
        key = (name, address)
        existing = by_name_address.get(key)
        if existing is None:
            by_name_address[key] = index
        else:
            union_find.union(index, existing)

    _union_spatial_matches(
        union_find,
        names,
        coordinates,
        coordinate_radius_m=coordinate_radius_m,
    )
    _union_poi_matches(
        union_find,
        materialized,
        names,
        coordinates,
        coordinate_radius_m=coordinate_radius_m,
    )

    clusters: dict[int, list[int]] = defaultdict(list)
    for index in range(len(materialized)):
        clusters[union_find.find(index)].append(index)

    return [
        _merge_cluster([materialized[index] for index in indexes])
        for indexes in clusters.values()
    ]


def detect_franchise(place_name: str, rules: FranchiseRules) -> str | None:
    """Return the configured franchise name when a place name matches an alias."""

    normalized_name = _normalize_franchise_text(place_name)
    folded_name = unicodedata.normalize("NFKC", place_name).lower()
    for brand in rules.brands:
        for alias in brand.aliases:
            normalized_alias = _normalize_franchise_text(alias)
            if _SHORT_ASCII_ALIAS.fullmatch(normalized_alias):
                pattern = re.compile(
                    rf"(?<![a-z0-9]){re.escape(normalized_alias)}(?=$|[^a-z0-9]|[가-힣])"
                )
                if pattern.search(folded_name):
                    return brand.name
            elif normalized_alias and normalized_alias in normalized_name:
                return brand.name
    return None


def detect_non_tourism_keyword(
    place_name: str,
    rules: NonTourismRules,
) -> str | None:
    """Return a configured keyword for explicit non-tourism facilities."""

    normalized_name = _normalize_franchise_text(place_name)
    for keyword in rules.name_keywords:
        if _normalize_franchise_text(keyword) in normalized_name:
            return keyword
    return None


def _union_spatial_matches(
    union_find: DisjointSet,
    names: Sequence[str],
    coordinates: Sequence[tuple[float | None, float | None]],
    *,
    coordinate_radius_m: float,
) -> None:
    buckets: dict[tuple[str, int, int], list[int]] = defaultdict(list)
    for index, (name, coordinate) in enumerate(zip(names, coordinates)):
        longitude, latitude = coordinate
        if not name or not _valid_coordinate(longitude, latitude):
            continue
        bucket_x, bucket_y = _bucket(longitude, latitude)
        for offset_x in (-1, 0, 1):
            for offset_y in (-1, 0, 1):
                for other_index in buckets.get(
                    (name, bucket_x + offset_x, bucket_y + offset_y), ()
                ):
                    other_longitude, other_latitude = coordinates[other_index]
                    if haversine_meters(
                        longitude,
                        latitude,
                        other_longitude,
                        other_latitude,
                    ) <= coordinate_radius_m:
                        union_find.union(index, other_index)
        buckets[(name, bucket_x, bucket_y)].append(index)


def _union_poi_matches(
    union_find: DisjointSet,
    rows: Sequence[Mapping[str, str]],
    names: Sequence[str],
    coordinates: Sequence[tuple[float | None, float | None]],
    *,
    coordinate_radius_m: float,
) -> None:
    spatial_buckets: dict[tuple[str, int, int], list[int]] = defaultdict(list)
    no_location: dict[tuple[str, str], int] = {}
    for index, row in enumerate(rows):
        poi_ids = _json_strings(row.get("aihub_poi_ids"))
        longitude, latitude = coordinates[index]
        for poi_id in poi_ids:
            if _valid_coordinate(longitude, latitude):
                bucket_x, bucket_y = _bucket(longitude, latitude)
                for offset_x in (-1, 0, 1):
                    for offset_y in (-1, 0, 1):
                        for other_index in spatial_buckets.get(
                            (poi_id, bucket_x + offset_x, bucket_y + offset_y), ()
                        ):
                            other_longitude, other_latitude = coordinates[other_index]
                            if haversine_meters(
                                longitude,
                                latitude,
                                other_longitude,
                                other_latitude,
                            ) <= coordinate_radius_m:
                                union_find.union(index, other_index)
                spatial_buckets[(poi_id, bucket_x, bucket_y)].append(index)
            elif names[index]:
                key = (poi_id, names[index])
                existing = no_location.get(key)
                if existing is None:
                    no_location[key] = index
                else:
                    union_find.union(index, existing)


def _merge_cluster(rows: Sequence[dict[str, str]]) -> dict[str, str]:
    representative = max(rows, key=_representative_key)
    merged = dict(representative)
    merged["aihub_visit_count"] = str(
        sum(_required_int(row.get("aihub_visit_count"), "aihub_visit_count") for row in rows)
    )

    aliases = set(_json_strings(representative.get("aihub_aliases")))
    representative_name = representative.get("aihub_place_name", "")
    for row in rows:
        aliases.update(_json_strings(row.get("aihub_aliases")))
        name = row.get("aihub_place_name", "")
        if name and name != representative_name:
            aliases.add(name)
    merged["aihub_aliases"] = json.dumps(sorted(aliases), ensure_ascii=False)

    poi_ids = {
        poi_id
        for row in rows
        for poi_id in _json_strings(row.get("aihub_poi_ids"))
    }
    merged["aihub_poi_ids"] = json.dumps(sorted(poi_ids), ensure_ascii=False)

    place_ids = sorted(
        _required_int(row.get("aihub_place_id"), "aihub_place_id") for row in rows
    )
    mapped_content_ids = {
        row.get("tourapi_content_id", "").strip()
        for row in rows
        if row.get("tourapi_content_id", "").strip()
    }
    merged["merged_aihub_place_ids"] = json.dumps(place_ids)
    merged["merged_aihub_place_count"] = str(len(place_ids))
    merged["merged_mapping_conflict"] = str(len(mapped_content_ids) > 1).lower()
    return merged


def _representative_key(row: Mapping[str, str]) -> tuple[int, int, int]:
    status_priority = _STATUS_PRIORITY.get(row.get("match_status", ""), 0)
    visit_count = _required_int(row.get("aihub_visit_count"), "aihub_visit_count")
    place_id = _required_int(row.get("aihub_place_id"), "aihub_place_id")
    return status_priority, visit_count, -place_id


def _output_sort_key(row: Mapping[str, str]) -> tuple[int, int, int]:
    return (
        -_STATUS_PRIORITY.get(row.get("match_status", ""), 0),
        -_required_int(row.get("aihub_visit_count"), "aihub_visit_count"),
        _required_int(row.get("aihub_place_id"), "aihub_place_id"),
    )


def _valid_coordinate(longitude: float | None, latitude: float | None) -> bool:
    return (
        longitude is not None
        and latitude is not None
        and math.isfinite(longitude)
        and math.isfinite(latitude)
        and 125.9 <= longitude <= 127.1
        and 33.0 <= latitude <= 34.0
    )


def _bucket(longitude: float, latitude: float) -> tuple[int, int]:
    return (
        math.floor(longitude / _SPATIAL_BUCKET_DEGREES),
        math.floor(latitude / _SPATIAL_BUCKET_DEGREES),
    )


def _normalize_franchise_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).lower()
    return _NON_ALPHANUMERIC.sub("", normalized)
