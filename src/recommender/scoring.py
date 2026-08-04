from __future__ import annotations

import math
from typing import Any, Iterable

from .models import (
    NormalizedItinerary,
    PackageCandidate,
    PackageItem,
    ScoreBreakdown,
    ScoredPackage,
)


def score_package(
    itinerary: NormalizedItinerary,
    package: PackageCandidate,
) -> ScoredPackage:
    if itinerary.duration_days != package.duration_days:
        raise ValueError("package duration must match itinerary duration")

    itinerary_by_id = _first_by_content_id(itinerary.tourism_stops)
    package_by_id = _first_by_content_id(package.tourism_items)
    itinerary_ids = set(itinerary_by_id)
    package_ids = set(package_by_id)
    matched_ids = itinerary_ids & package_ids

    coverage = len(matched_ids) / len(itinerary_ids) if itinerary_ids else 0.0
    precision = len(matched_ids) / len(package_ids) if package_ids else 0.0
    exact_overlap = 70.0 * ((coverage * 0.8) + (precision * 0.2))
    route_fit = _route_fit(matched_ids, itinerary_by_id, package_by_id)
    profile_fit = _profile_fit(itinerary.conditions, package.match_profile)
    nearby_fit, nearby_evidence = _nearby_fit(
        itinerary_by_id, package.tourism_items, matched_ids
    )
    total = exact_overlap + route_fit + profile_fit + nearby_fit

    return ScoredPackage(
        package=package,
        score=ScoreBreakdown(
            exact_overlap=round(exact_overlap, 2),
            route_fit=round(route_fit, 2),
            profile_fit=round(profile_fit, 2),
            nearby_fit=round(nearby_fit, 2),
            total=round(total, 2),
        ),
        exact_match_count=len(matched_ids),
        itinerary_place_count=len(itinerary_ids),
        matched_content_ids=tuple(sorted(matched_ids)),
        unmatched_content_ids=tuple(sorted(itinerary_ids - package_ids)),
        evidence={
            "itinerary_coverage": round(coverage, 4),
            "package_precision": round(precision, 4),
            **nearby_evidence,
        },
    )


def deterministic_sort_key(candidate: ScoredPackage) -> tuple[Any, ...]:
    """Exact place count is deliberately more important than every other score."""

    return (
        -candidate.exact_match_count,
        -candidate.overlap_ratio,
        -candidate.score.total,
        candidate.package.package_id,
    )


def _route_fit(
    matched_ids: set[int],
    itinerary_by_id: dict[int, Any],
    package_by_id: dict[int, Any],
) -> float:
    if not matched_ids:
        return 0.0
    same_day = sum(
        itinerary_by_id[content_id].day == package_by_id[content_id].day
        for content_id in matched_ids
    ) / len(matched_ids)

    ordered_ids = sorted(
        matched_ids,
        key=lambda content_id: (
            itinerary_by_id[content_id].day,
            itinerary_by_id[content_id].sequence,
        ),
    )
    if len(ordered_ids) < 2:
        order_ratio = 1.0
    else:
        concordant = 0
        pair_count = 0
        for left_index, left_id in enumerate(ordered_ids):
            for right_id in ordered_ids[left_index + 1 :]:
                left = package_by_id[left_id]
                right = package_by_id[right_id]
                pair_count += 1
                if (left.day, left.sequence or 0) <= (right.day, right.sequence or 0):
                    concordant += 1
        order_ratio = concordant / pair_count
    return (same_day * 10.0) + (order_ratio * 5.0)


def _profile_fit(conditions: dict[str, Any], profile: dict[str, Any]) -> float:
    party = str(conditions.get("party_type") or "").strip().lower()
    pace = str(conditions.get("pace") or "").strip().lower()
    themes = _as_set(
        conditions.get("preferred_visit_types")
        or conditions.get("themes")
        or conditions.get("preferred_themes")
    )

    party_values = _profile_set(profile, "party_types", "party_type")
    pace_values = _profile_set(profile, "paces", "pace")
    theme_values = _profile_set(profile, "themes", "preferred_visit_types")
    party_score = 4.0 if party and party in party_values else 0.0
    pace_score = 2.0 if pace and pace in pace_values else 0.0
    theme_score = 0.0
    if themes and theme_values:
        theme_score = 4.0 * len(themes & theme_values) / len(themes)
    return party_score + pace_score + theme_score


def _nearby_fit(
    itinerary_by_id: dict[int, Any],
    package_items: tuple[PackageItem, ...],
    matched_ids: set[int],
) -> tuple[float, dict[str, Any]]:
    unmatched = [
        stop
        for content_id, stop in itinerary_by_id.items()
        if content_id not in matched_ids
        and stop.longitude is not None
        and stop.latitude is not None
    ]
    package_locations = [
        item
        for item in package_items
        if item.longitude is not None and item.latitude is not None
    ]
    if not unmatched or not package_locations:
        return 0.0, {"nearby_within_10km_count": 0}

    distances = [
        min(
            _haversine_km(
                stop.longitude,
                stop.latitude,
                item.longitude,
                item.latitude,
            )
            for item in package_locations
        )
        for stop in unmatched
    ]
    nearby_count = sum(distance <= 10.0 for distance in distances)
    score = 5.0 * nearby_count / len(unmatched)
    return score, {
        "nearby_within_10km_count": nearby_count,
        "unmatched_with_coordinates_count": len(unmatched),
        "average_nearest_distance_km": round(sum(distances) / len(distances), 2),
    }


def _first_by_content_id(rows: Iterable[Any]) -> dict[int, Any]:
    result: dict[int, Any] = {}
    for row in rows:
        result.setdefault(int(row.content_id), row)
    return result


def _profile_set(profile: dict[str, Any], *keys: str) -> set[str]:
    values: set[str] = set()
    containers = [profile]
    for nested in ("preferred", "required"):
        value = profile.get(nested)
        if isinstance(value, dict):
            containers.append(value)
    for container in containers:
        for key in keys:
            values.update(_as_set(container.get(key)))
    return values


def _as_set(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {value.strip().lower()} if value.strip() else set()
    if isinstance(value, (list, tuple, set)):
        return {str(item).strip().lower() for item in value if str(item).strip()}
    return {str(value).strip().lower()}


def _haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (lon1, lat1, lon2, lat2))
    delta_lon = lon2 - lon1
    delta_lat = lat2 - lat1
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return 6371.0088 * 2 * math.asin(math.sqrt(value))
