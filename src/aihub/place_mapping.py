from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
import math
import re
import unicodedata
from typing import Iterable


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


class _UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if self.rank[left_root] < self.rank[right_root]:
            left_root, right_root = right_root, left_root
        self.parent[right_root] = left_root
        if self.rank[left_root] == self.rank[right_root]:
            self.rank[left_root] += 1


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
    union_find: _UnionFind,
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
    union_find = _UnionFind(len(records))
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
        aliases = tuple(sorted({record.name for record in group_records if record.name != canonical_name}))
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
        elif len({normalized_addresses[index] for index in indexes if normalized_addresses[index]}) == 1:
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


class TourPlaceMatcher:
    def __init__(self, places: Iterable[TourPlaceCandidate]) -> None:
        self.places = tuple(places)
        self._by_content_id = {place.content_id: place for place in self.places}
        self._by_name: dict[str, list[TourPlaceCandidate]] = defaultdict(list)
        self._by_address: dict[str, list[TourPlaceCandidate]] = defaultdict(list)
        self._by_bucket: dict[tuple[int, int], list[TourPlaceCandidate]] = defaultdict(list)
        self._by_name_bigram: dict[str, dict[int, TourPlaceCandidate]] = defaultdict(dict)
        for place in self.places:
            for name in (place.title, *place.aliases):
                for normalized in _name_variants(name):
                    self._by_name[normalized].append(place)
                    for bigram in _name_bigrams(normalized):
                        self._by_name_bigram[bigram][place.content_id] = place
            address = normalize_address(place.address)
            if address:
                self._by_address[address].append(place)
            if valid_jeju_coordinate(place.longitude, place.latitude):
                self._by_bucket[
                    _bucket(place.longitude, place.latitude, _MATCH_BUCKET_DEGREES)
                ].append(place)

    def match(self, place: GroupedAIHubPlace) -> PlaceMappingResult:
        names: set[str] = set()
        for name in (place.canonical_name, *place.aliases):
            names.update(_name_variants(name))
        address = normalize_address(place.road_address) or normalize_address(place.lot_address)
        candidates: dict[int, TourPlaceCandidate] = {}
        for name in names:
            for candidate in self._by_name.get(name, ()):
                candidates[candidate.content_id] = candidate
            shared_bigrams: Counter[int] = Counter()
            bigrams = _name_bigrams(name)
            for bigram in bigrams:
                shared_bigrams.update(self._by_name_bigram.get(bigram, {}).keys())
            minimum_shared = 1 if len(bigrams) <= 2 else 2
            for content_id, shared_count in shared_bigrams.items():
                if shared_count >= minimum_shared:
                    candidates[content_id] = self._by_content_id[content_id]
        if address:
            for candidate in self._by_address.get(address, ()):
                candidates[candidate.content_id] = candidate
        if valid_jeju_coordinate(place.longitude, place.latitude):
            center_x, center_y = _bucket(
                place.longitude,
                place.latitude,
                _MATCH_BUCKET_DEGREES,
            )
            for offset_x in range(-2, 3):
                for offset_y in range(-2, 3):
                    for candidate in self._by_bucket.get(
                        (center_x + offset_x, center_y + offset_y), ()
                    ):
                        if not valid_jeju_coordinate(candidate.longitude, candidate.latitude):
                            continue
                        distance = haversine_meters(
                            place.longitude,
                            place.latitude,
                            candidate.longitude,
                            candidate.latitude,
                        )
                        if distance <= _MATCH_RADIUS_METERS:
                            candidates[candidate.content_id] = candidate

        ranked = [self._score(place, candidate) for candidate in candidates.values()]
        ranked.sort(key=lambda item: (-item[0], item[2] if item[2] is not None else math.inf))
        if not ranked:
            return self._unmatched(place)

        score, candidate, distance, similarity, exact_name, address_match = ranked[0]
        runner_score = ranked[1][0] if len(ranked) > 1 else 0.0
        margin = score - runner_score

        if exact_name and address_match:
            return self._result(place, candidate, "MATCHED", "EXACT_NAME_ADDRESS", similarity, distance, max(score, 0.99))
        if exact_name and distance is not None and distance <= 150.0:
            return self._result(place, candidate, "MATCHED", "EXACT_NAME_COORD", similarity, distance, max(score, 0.97))
        if address_match and similarity >= 0.82 and (distance is None or distance <= 1000.0):
            return self._result(place, candidate, "REVIEW", "FUZZY_NAME_REVIEW", similarity, distance, score)
        if exact_name:
            return self._result(place, candidate, "REVIEW", "EXACT_NAME_REVIEW", similarity, distance, score)
        if distance is not None and distance <= 250.0 and similarity >= 0.75 and margin >= 0.03:
            return self._result(place, candidate, "REVIEW", "FUZZY_NAME_REVIEW", similarity, distance, score)
        return self._unmatched(place)

    @staticmethod
    def _score(
        place: GroupedAIHubPlace,
        candidate: TourPlaceCandidate,
    ) -> tuple[float, TourPlaceCandidate, float | None, float, bool, bool]:
        source_names = set().union(
            *(_name_variants(value) for value in (place.canonical_name, *place.aliases))
        )
        candidate_names = set().union(
            *(_name_variants(value) for value in (candidate.title, *candidate.aliases))
        )
        similarities = [
            SequenceMatcher(None, source, target).ratio()
            for source in source_names
            for target in candidate_names
            if source and target
        ]
        similarity = max(similarities, default=0.0)
        exact_name = any(source == target for source in source_names for target in candidate_names if source and target)
        source_address = normalize_address(place.road_address) or normalize_address(place.lot_address)
        target_address = normalize_address(candidate.address)
        address_match = bool(source_address and target_address and source_address == target_address)

        distance = None
        if valid_jeju_coordinate(place.longitude, place.latitude) and valid_jeju_coordinate(candidate.longitude, candidate.latitude):
            distance = haversine_meters(
                place.longitude,
                place.latitude,
                candidate.longitude,
                candidate.latitude,
            )
        distance_score = 0.0 if distance is None else max(0.0, 1.0 - distance / 500.0)
        score = similarity * 0.78 + distance_score * 0.22
        if address_match:
            score = min(1.0, score + 0.08)
        return score, candidate, distance, similarity, exact_name, address_match

    @staticmethod
    def _result(
        place: GroupedAIHubPlace,
        candidate: TourPlaceCandidate,
        status: str,
        method: str,
        similarity: float,
        distance: float | None,
        confidence: float,
    ) -> PlaceMappingResult:
        return PlaceMappingResult(
            aihub_place_id=place.aihub_place_id,
            tourapi_content_id=candidate.content_id,
            status=status,
            method=method,
            name_similarity=round(similarity, 4),
            distance_m=round(distance, 2) if distance is not None else None,
            confidence_score=round(min(confidence, 1.0), 4),
        )

    @staticmethod
    def _unmatched(place: GroupedAIHubPlace) -> PlaceMappingResult:
        return PlaceMappingResult(
            aihub_place_id=place.aihub_place_id,
            tourapi_content_id=None,
            status="UNMATCHED",
            method="NO_RELIABLE_CANDIDATE",
            name_similarity=None,
            distance_m=None,
            confidence_score=0.0,
        )
