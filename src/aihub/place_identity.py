from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import math
import re
import unicodedata
from typing import Iterable

from src.common.disjoint_set import DisjointSet


_NON_WORD = re.compile(r"[^0-9a-z가-힣]+")
_PARENTHETICAL = re.compile(r"\([^)]*\)")
_BRACKETED_NAME = re.compile(r"[\(\[\{（]([^\)\]\}）]*)[\)\]\}）]")
_PROVINCE = re.compile(r"제주특별자치도|제주도")
_GROUP_RADIUS_METERS = 75.0
_GROUP_BUCKET_DEGREES = 0.001
_MATCH_BUCKET_DEGREES = 0.003
_MATCH_RADIUS_METERS = 500.0


@dataclass(frozen=True)
class VisitPlaceRecord:
    travel_id: str
    visit_area_id: str
    name: str
    poi_name: str | None
    road_address: str | None
    lot_address: str | None
    longitude: float | None
    latitude: float | None
    poi_id: str | None
    visit_area_type_cd: str


@dataclass(frozen=True)
class GroupedAIHubPlace:
    aihub_place_id: int
    canonical_name: str
    normalized_name: str
    aliases: tuple[str, ...]
    poi_ids: tuple[str, ...]
    road_address: str | None
    lot_address: str | None
    longitude: float | None
    latitude: float | None
    visit_area_type_cd: str
    visit_count: int
    identity_method: str
    member_keys: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class TourPlaceCandidate:
    content_id: int
    title: str
    aliases: tuple[str, ...]
    address: str | None
    longitude: float | None
    latitude: float | None


@dataclass(frozen=True)
class PlaceMappingResult:
    aihub_place_id: int
    tourapi_content_id: int | None
    status: str
    method: str
    name_similarity: float | None
    distance_m: float | None
    confidence_score: float


def normalize_name(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKC", value).lower()
    return _NON_WORD.sub("", normalized)


def _name_variants(value: str | None) -> set[str]:
    """Return conservative comparison variants without changing stored names."""
    if not value:
        return set()
    raw_variants = {value, _BRACKETED_NAME.sub("", value)}
    raw_variants.update(match.group(1) for match in _BRACKETED_NAME.finditer(value))
    normalized = {normalize_name(item) for item in raw_variants if normalize_name(item)}
    variants = set(normalized)
    for item in normalized:
        if item.startswith("제주") and len(item) > 4:
            variants.add(item[2:])
        variants.add(item.replace("해수욕장", "해변"))
        variants.add(item.replace("재래시장", "시장"))
    return {item for item in variants if item}


def _name_bigrams(value: str) -> set[str]:
    if len(value) < 2:
        return {value} if value else set()
    return {value[index : index + 2] for index in range(len(value) - 1)}


def normalize_address(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKC", value).lower()
    normalized = _PARENTHETICAL.sub("", normalized)
    normalized = _PROVINCE.sub("", normalized)
    return _NON_WORD.sub("", normalized)


def valid_jeju_coordinate(longitude: float | None, latitude: float | None) -> bool:
    return (
        longitude is not None
        and latitude is not None
        and 125.9 <= longitude <= 127.1
        and 33.0 <= latitude <= 34.0
    )


def haversine_meters(
    longitude_a: float,
    latitude_a: float,
    longitude_b: float,
    latitude_b: float,
) -> float:
    earth_radius = 6_371_008.8
    lat_a = math.radians(latitude_a)
    lat_b = math.radians(latitude_b)
    delta_lat = lat_b - lat_a
    delta_lon = math.radians(longitude_b - longitude_a)
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2) ** 2
    )
    return earth_radius * 2 * math.asin(math.sqrt(value))


def _bucket(
    longitude: float,
    latitude: float,
    bucket_size: float,
) -> tuple[int, int]:
    return math.floor(longitude / bucket_size), math.floor(latitude / bucket_size)


def _union_same_value(
    union_find: DisjointSet,
    indexes: Iterable[int],
) -> None:
    values = list(indexes)
    for index in values[1:]:
        union_find.union(values[0], index)


def _most_common(values: Iterable[str]) -> str:
    counter = Counter(value for value in values if value)
    if not counter:
        return ""
    return sorted(counter.items(), key=lambda item: (-item[1], -len(item[0]), item[0]))[0][0]


def _median(values: Iterable[float]) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def group_aihub_visits(
    visits: Iterable[VisitPlaceRecord],
    *,
    coordinate_radius_m: float = _GROUP_RADIUS_METERS,
) -> tuple[list[GroupedAIHubPlace], dict[tuple[str, str], int]]:
    records = list(visits)
    union_find = DisjointSet(len(records))
    normalized_names = [normalize_name(record.name) for record in records]
    normalized_addresses = [
        normalize_address(record.road_address) or normalize_address(record.lot_address)
        for record in records
    ]

    by_name_address: dict[tuple[str, str], list[int]] = defaultdict(list)
    no_location_by_poi_name: dict[tuple[str, str], list[int]] = defaultdict(list)
    spatial_by_name: dict[tuple[str, int, int], list[int]] = defaultdict(list)
    spatial_by_poi: dict[tuple[str, int, int], list[int]] = defaultdict(list)

    for index, record in enumerate(records):
        name = normalized_names[index]
        address = normalized_addresses[index]
        if name and address:
            by_name_address[(name, address)].append(index)
        if valid_jeju_coordinate(record.longitude, record.latitude):
            bucket_x, bucket_y = _bucket(
                record.longitude,
                record.latitude,
                _GROUP_BUCKET_DEGREES,
            )
            if name:
                spatial_by_name[(name, bucket_x, bucket_y)].append(index)
            if record.poi_id:
                spatial_by_poi[(record.poi_id, bucket_x, bucket_y)].append(index)
        elif record.poi_id and name:
            no_location_by_poi_name[(record.poi_id, name)].append(index)

    for indexes in by_name_address.values():
        _union_same_value(union_find, indexes)
    for indexes in no_location_by_poi_name.values():
        _union_same_value(union_find, indexes)

    def union_spatial(index: int, keys: list[tuple[str, int, int]], source: dict) -> None:
        record = records[index]
        for key_prefix, center_x, center_y in keys:
            for offset_x in (-1, 0, 1):
                for offset_y in (-1, 0, 1):
                    for other_index in source.get(
                        (key_prefix, center_x + offset_x, center_y + offset_y), ()
                    ):
                        if other_index >= index:
                            continue
                        other = records[other_index]
                        distance = haversine_meters(
                            record.longitude,
                            record.latitude,
                            other.longitude,
                            other.latitude,
                        )
                        if distance <= coordinate_radius_m:
                            union_find.union(index, other_index)

    for index, record in enumerate(records):
        if not valid_jeju_coordinate(record.longitude, record.latitude):
            continue
        center_x, center_y = _bucket(
            record.longitude,
            record.latitude,
            _GROUP_BUCKET_DEGREES,
        )
        name = normalized_names[index]
        if name:
            union_spatial(index, [(name, center_x, center_y)], spatial_by_name)
        if record.poi_id:
            union_spatial(index, [(record.poi_id, center_x, center_y)], spatial_by_poi)

    members_by_root: dict[int, list[int]] = defaultdict(list)
    for index in range(len(records)):
        members_by_root[union_find.find(index)].append(index)

    group_data: list[tuple[tuple[str, str, str], list[int], dict[str, object]]] = []
    for indexes in members_by_root.values():
        group_records = [records[index] for index in indexes]
        canonical_name = _most_common(record.name for record in group_records)
        aliases = tuple(
            sorted(
                record.name
                for record in group_records
                if record.name != canonical_name
            )
        )
        poi_ids = tuple(sorted({record.poi_id for record in group_records if record.poi_id}))
        road_address = _most_common(record.road_address or "" for record in group_records) or None
        lot_address = _most_common(record.lot_address or "" for record in group_records) or None
        valid_records = [
            record
            for record in group_records
            if valid_jeju_coordinate(record.longitude, record.latitude)
        ]
        longitude = _median(record.longitude for record in valid_records)
        latitude = _median(record.latitude for record in valid_records)
        visit_type = _most_common(record.visit_area_type_cd for record in group_records)

        if len(indexes) == 1:
            identity_method = "UNIQUE_VISIT"
        elif len(poi_ids) == 1:
            identity_method = "POI_CONFIRMED"
        elif len(
            {
                normalized_addresses[index]
                for index in indexes
                if normalized_addresses[index]
            }
        ) == 1:
            identity_method = "NAME_ADDRESS"
        else:
            identity_method = "NAME_COORDINATE"

        member_keys = tuple(
            sorted((record.travel_id, record.visit_area_id) for record in group_records)
        )
        sort_key = (
            normalize_name(canonical_name),
            normalize_address(road_address) or normalize_address(lot_address),
            "|".join(member_keys[0]),
        )
        group_data.append(
            (
                sort_key,
                indexes,
                {
                    "canonical_name": canonical_name,
                    "aliases": aliases,
                    "poi_ids": poi_ids,
                    "road_address": road_address,
                    "lot_address": lot_address,
                    "longitude": longitude,
                    "latitude": latitude,
                    "visit_type": visit_type,
                    "identity_method": identity_method,
                    "member_keys": member_keys,
                },
            )
        )

    grouped_places: list[GroupedAIHubPlace] = []
    visit_membership: dict[tuple[str, str], int] = {}
    for place_id, (_, _, data) in enumerate(sorted(group_data), start=1):
        place = GroupedAIHubPlace(
            aihub_place_id=place_id,
            canonical_name=data["canonical_name"],
            normalized_name=normalize_name(data["canonical_name"]),
            aliases=data["aliases"],
            poi_ids=data["poi_ids"],
            road_address=data["road_address"],
            lot_address=data["lot_address"],
            longitude=data["longitude"],
            latitude=data["latitude"],
            visit_area_type_cd=data["visit_type"],
            visit_count=len(data["member_keys"]),
            identity_method=data["identity_method"],
            member_keys=data["member_keys"],
        )
        grouped_places.append(place)
        for member_key in place.member_keys:
            visit_membership[member_key] = place_id

    return grouped_places, visit_membership
