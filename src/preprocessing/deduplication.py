from __future__ import annotations

from collections import defaultdict
import math
import re
from typing import Any, Mapping, Sequence

from .cleaner import clean_text, first_value, validated_coordinates
from .models import PlaceGroup, PlaceGroupMember, PlaceGroupingResult


MAX_SAME_VENUE_DISTANCE_METERS = 75.0
PARENTHETICAL_PATTERN = re.compile(r"\([^)]*\)")
TITLE_QUALIFIER_PATTERN = re.compile(
    r"\((?!\s*[ab]\s*\))[^)]*\)|\[[^]]*\]", re.IGNORECASE
)
NON_WORD_PATTERN = re.compile(r"[^0-9a-z가-힣]+", re.IGNORECASE)


def group_duplicate_places(
    rows: Sequence[Mapping[str, Any]],
    *,
    title_aliases: Mapping[str, str] | None = None,
) -> PlaceGroupingResult:
    normalized_aliases = {
        normalize_place_title(alias): normalize_place_title(canonical)
        for alias, canonical in (title_aliases or {}).items()
    }
    rows_by_title: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        normalized_title = normalize_place_title(first_value(row, "common_title", "title"))
        normalized_title = normalized_aliases.get(normalized_title, normalized_title)
        if normalized_title:
            rows_by_title[normalized_title].append(row)

    groups: list[PlaceGroup] = []
    memberships: dict[str, PlaceGroupMember] = {}
    for normalized_title, candidates in rows_by_title.items():
        if len(candidates) < 2:
            continue
        for component in _same_venue_components(candidates):
            if len(component) < 2:
                continue
            group = _build_group(normalized_title, component)
            groups.append(group)
            for member in group.members:
                memberships[member.content_id] = member

    groups.sort(key=lambda group: _content_id_sort_key(group.canonical_content_id))
    return PlaceGroupingResult(tuple(groups), memberships)


def normalize_place_title(value: str) -> str:
    without_qualifier = TITLE_QUALIFIER_PATTERN.sub("", clean_text(value).lower())
    return NON_WORD_PATTERN.sub("", without_qualifier)


def normalize_place_address(value: str) -> str:
    without_parenthetical = PARENTHETICAL_PATTERN.sub("", clean_text(value).lower())
    return NON_WORD_PATTERN.sub("", without_parenthetical)


def place_groups_payload(groups: Sequence[PlaceGroup]) -> list[dict[str, Any]]:
    return [
        {
            "place_group_id": group.place_group_id,
            "canonical_contentid": group.canonical_content_id,
            "normalized_title": group.normalized_title,
            "members": [
                {
                    "contentid": member.content_id,
                    "dataset": member.dataset,
                    "relationship_type": member.relationship_type,
                    "is_primary_place": member.is_primary_place,
                }
                for member in group.members
            ],
        }
        for group in groups
    ]


def _same_venue_components(
    rows: Sequence[Mapping[str, Any]],
) -> list[list[Mapping[str, Any]]]:
    parents = list(range(len(rows)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    for left in range(len(rows)):
        for right in range(left + 1, len(rows)):
            if _same_physical_location(rows[left], rows[right]):
                union(left, right)

    components: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for index, row in enumerate(rows):
        components[find(index)].append(row)
    return list(components.values())


def _same_physical_location(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> bool:
    left_address = normalize_place_address(first_value(left, "common_addr1", "addr1"))
    right_address = normalize_place_address(first_value(right, "common_addr1", "addr1"))
    if left_address and left_address == right_address:
        return True

    left_coordinates = _coordinates(left)
    right_coordinates = _coordinates(right)
    if left_coordinates is None or right_coordinates is None:
        return False
    return _distance_meters(left_coordinates, right_coordinates) <= MAX_SAME_VENUE_DISTANCE_METERS


def _build_group(
    normalized_title: str,
    rows: Sequence[Mapping[str, Any]],
) -> PlaceGroup:
    primary = min(rows, key=lambda row: _primary_sort_key(row, normalized_title))
    canonical_content_id = first_value(primary, "contentid", "contentId")
    primary_dataset = first_value(primary, "dataset") or "tourism"
    place_group_id = f"tourapi-group:{canonical_content_id}"

    members: list[PlaceGroupMember] = []
    for row in sorted(
        rows,
        key=lambda item: _content_id_sort_key(first_value(item, "contentid", "contentId")),
    ):
        content_id = first_value(row, "contentid", "contentId")
        dataset = first_value(row, "dataset") or "tourism"
        is_primary = content_id == canonical_content_id
        members.append(
            PlaceGroupMember(
                content_id=content_id,
                dataset=dataset,
                place_group_id=place_group_id,
                canonical_content_id=canonical_content_id,
                relationship_type=_relationship_type(
                    dataset, primary_dataset, is_primary=is_primary
                ),
                is_primary_place=is_primary,
            )
        )

    return PlaceGroup(
        place_group_id=place_group_id,
        canonical_content_id=canonical_content_id,
        normalized_title=normalized_title,
        members=tuple(members),
    )


def _primary_sort_key(
    row: Mapping[str, Any], canonical_title: str
) -> tuple[int, int, int, tuple[int, str]]:
    dataset = first_value(row, "dataset") or "tourism"
    dataset_priority = 0 if dataset == "tourism" else 1
    normalized_title = normalize_place_title(first_value(row, "common_title", "title"))
    title_priority = 0 if normalized_title == canonical_title else 1
    completeness = sum(
        bool(first_value(row, field))
        for field in (
            "common_overview",
            "common_firstimage",
            "common_homepage",
            "intro_fetch_status",
        )
    )
    content_id = first_value(row, "contentid", "contentId")
    return dataset_priority, title_priority, -completeness, _content_id_sort_key(content_id)


def _relationship_type(
    dataset: str,
    primary_dataset: str,
    *,
    is_primary: bool,
) -> str:
    if is_primary:
        return "primary"
    if dataset == primary_dataset:
        return "exact_duplicate"
    return {
        "shopping": "onsite_shopping",
        "food": "onsite_food",
        "lodging": "onsite_lodging",
    }.get(dataset, "same_venue")


def _coordinates(row: Mapping[str, Any]) -> tuple[float, float] | None:
    longitude, latitude = validated_coordinates(
        first_value(row, "common_mapx", "mapx"),
        first_value(row, "common_mapy", "mapy"),
    )
    if longitude is None or latitude is None:
        return None
    return longitude, latitude


def _distance_meters(
    left: tuple[float, float],
    right: tuple[float, float],
) -> float:
    left_lon, left_lat = map(math.radians, left)
    right_lon, right_lat = map(math.radians, right)
    delta_lon = right_lon - left_lon
    delta_lat = right_lat - left_lat
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(left_lat) * math.cos(right_lat) * math.sin(delta_lon / 2) ** 2
    )
    return 6_371_000 * 2 * math.asin(math.sqrt(haversine))


def _content_id_sort_key(content_id: str) -> tuple[int, str]:
    return (int(content_id), content_id) if content_id.isdigit() else (2**63 - 1, content_id)
