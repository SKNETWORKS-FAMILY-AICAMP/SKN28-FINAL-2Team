from __future__ import annotations

from datetime import date, datetime
import math
from typing import Any, Iterable

from .models import (
    NormalizedItinerary,
    PackageCandidate,
    PackageItem,
    ScoreBreakdown,
    ScoredPackage,
)
from .profile_mapping import (
    condition_category_groups,
    normalize_companion_types,
    normalize_condition_companions,
    normalize_condition_categories,
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
    # 50 points: the generated itinerary should still be the strongest signal.
    exact_overlap = 50.0 * ((coverage * 0.8) + (precision * 0.2))
    route_fit = _route_fit(matched_ids, itinerary_by_id, package_by_id)
    profile_fit, profile_evidence = _profile_fit(
        itinerary.conditions,
        package.companion_types,
        package.place_categories,
        package.title,
    )
    nearby_fit, nearby_evidence = _regional_proximity_fit(
        itinerary_by_id, package.tourism_items
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
            **profile_evidence,
            **nearby_evidence,
        },
    )


def deterministic_sort_key(candidate: ScoredPackage) -> tuple[Any, ...]:
    """Rank by the requested weighted score, then use overlap as a tie-breaker."""

    return (
        -candidate.score.total,
        -candidate.exact_match_count,
        -candidate.overlap_ratio,
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
    # 6 of the 10 region/route points are assigned to day and visit order.
    return (same_day * 4.0) + (order_ratio * 2.0)


def _profile_fit(
    conditions: dict[str, Any],
    package_companions: Iterable[str],
    package_categories: Iterable[str],
    package_title: str,
) -> tuple[float, dict[str, Any]]:
    condition_companions = normalize_condition_companions(
        conditions.get("companion_types")
        or conditions.get("companion_type")
        or conditions.get("party_type")
    )
    raw_categories = (
        conditions.get("preferred_visit_types")
        or conditions.get("place_categories")
        or conditions.get("themes")
        or conditions.get("preferred_themes")
    )
    profile_companions = set(normalize_companion_types(package_companions))
    profile_categories = normalize_condition_categories(package_categories)

    matched_companions = condition_companions & profile_companions
    companion_score = 20.0 if matched_companions else 0.0
    category_groups = condition_category_groups(raw_categories)
    matched_groups = [
        group for group in category_groups if group & profile_categories
    ]
    category_score = (
        15.0 * len(matched_groups) / len(category_groups)
        if category_groups and profile_categories
        else 0.0
    )
    matched_categories = (
        set().union(*(group & profile_categories for group in matched_groups))
        if matched_groups
        else set()
    )
    requested_season = _season_from_start_date(conditions.get("start_date"))
    package_seasons = _seasons_from_title(package_title)
    # Titles without a season are valid all year. Older callers without a
    # start_date also keep these five points neutral for compatibility.
    season_match = (
        requested_season is None
        or not package_seasons
        or requested_season in package_seasons
    )
    season_score = 5.0 if season_match else 0.0
    total = companion_score + category_score + season_score
    return total, {
        "companion_score": round(companion_score, 2),
        "category_score": round(category_score, 2),
        "season_score": round(season_score, 2),
        "requested_season": requested_season,
        "package_seasons": sorted(package_seasons),
        "season_match": season_match,
        "matched_companion_types": sorted(matched_companions),
        "matched_place_categories": sorted(matched_categories),
    }


_SEASON_TITLE_MARKERS = {
    "spring": ("봄",),
    "summer": ("여름",),
    "autumn": ("가을",),
    "winter": ("겨울",),
}


def _season_from_start_date(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        parsed = value.date()
    elif isinstance(value, date):
        parsed = value
    else:
        try:
            parsed = date.fromisoformat(str(value)[:10])
        except ValueError:
            return None
    if 3 <= parsed.month <= 5:
        return "spring"
    if 6 <= parsed.month <= 8:
        return "summer"
    if 9 <= parsed.month <= 11:
        return "autumn"
    return "winter"


def _seasons_from_title(title: str) -> set[str]:
    normalized = str(title or "").strip().lower()
    return {
        season
        for season, markers in _SEASON_TITLE_MARKERS.items()
        if any(marker in normalized for marker in markers)
    }


def _regional_proximity_fit(
    itinerary_by_id: dict[int, Any],
    package_items: tuple[PackageItem, ...],
) -> tuple[float, dict[str, Any]]:
    itinerary_locations = [
        stop
        for stop in itinerary_by_id.values()
        if stop.longitude is not None and stop.latitude is not None
    ]
    package_locations = [
        item
        for item in package_items
        if item.longitude is not None and item.latitude is not None
    ]
    if not itinerary_locations or not package_locations:
        return 0.0, {"regional_within_10km_count": 0}

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
        for stop in itinerary_locations
    ]
    nearby_count = sum(distance <= 10.0 for distance in distances)
    # 4 of the 10 region/route points measure geographic proximity.
    score = 4.0 * nearby_count / len(itinerary_locations)
    return score, {
        "regional_within_10km_count": nearby_count,
        "itinerary_places_with_coordinates_count": len(itinerary_locations),
        "average_nearest_distance_km": round(sum(distances) / len(distances), 2),
    }


def _first_by_content_id(rows: Iterable[Any]) -> dict[int, Any]:
    result: dict[int, Any] = {}
    for row in rows:
        result.setdefault(int(row.content_id), row)
    return result


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