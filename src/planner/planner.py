from __future__ import annotations

import re
from typing import Iterable, Mapping, Sequence

from ..common.geo import haversine_km
from ..models.itinerary import SlotCandidate
from ..models.travel_condition import TravelCondition
from ..rag.models import RetrievedPlace
from .config import VISIT_PREFERENCE_KEYWORDS, PlannerConfig

_WHITESPACE_RE = re.compile(r"\s+")


def select_candidates(
    places: Sequence[RetrievedPlace],
    condition: TravelCondition,
    *,
    role: str,
    location_hint: Mapping[str, float] | None = None,
    exclude_content_ids: Iterable[int] = (),
    limit: int | None = None,
    config: PlannerConfig | None = None,
) -> list[SlotCandidate]:
    """Return the best ``limit`` candidates for one itinerary slot."""

    config = config or PlannerConfig()
    excluded_ids = set(exclude_content_ids)
    limit = limit if limit is not None else config.limit_for(role)
    radius_km = config.radius_for(condition.local_transport)

    deduped = _deduplicate(places)
    scored: list[tuple[float, RetrievedPlace, float | None]] = []
    for place in deduped:
        if place.content_id in excluded_ids:
            continue
        if _matches_excluded_place(place, condition.excluded_places):
            continue

        distance_km = haversine_km(
            location_hint.get("latitude") if location_hint else None,
            location_hint.get("longitude") if location_hint else None,
            place.latitude,
            place.longitude,
        )
        if distance_km is not None and distance_km > radius_km:
            continue

        proximity_score = (
            0.5 if distance_km is None else max(0.0, 1.0 - (distance_km / radius_km))
        )
        similarity_score = _clamp(place.similarity_score if place.similarity_score is not None else 0.5)
        style_score = _style_fit_score(place, condition)

        final_score = (
            similarity_score * config.similarity_weight
            + proximity_score * config.proximity_weight
            + style_score * config.style_weight
        )
        scored.append((final_score, place, distance_km))

    scored.sort(key=lambda item: item[0], reverse=True)

    return [
        SlotCandidate(
            content_id=place.content_id,
            title=place.title,
            final_score=round(final_score, 4),
            similarity_score=place.similarity_score,
            place=place.to_dict(),
        )
        for final_score, place, _distance_km in scored[:limit]
    ]


def _deduplicate(places: Sequence[RetrievedPlace]) -> list[RetrievedPlace]:
    best_by_key: dict[str, RetrievedPlace] = {}
    seen_content_ids: set[int] = set()
    for place in places:
        if place.content_id in seen_content_ids:
            continue
        key = _normalized_title(place.title)
        current = best_by_key.get(key)
        if current is None or _rank_key(place) > _rank_key(current):
            best_by_key[key] = place
        seen_content_ids.add(place.content_id)
    return list(best_by_key.values())


def _rank_key(place: RetrievedPlace) -> float:
    return place.similarity_score if place.similarity_score is not None else 0.0


def _normalized_title(title: str) -> str:
    return _WHITESPACE_RE.sub("", title).strip().lower()


def _matches_excluded_place(place: RetrievedPlace, excluded_places: Sequence[str]) -> bool:
    title = _normalized_title(place.title)
    return any(_normalized_title(excluded) in title for excluded in excluded_places if excluded)


def _style_fit_score(place: RetrievedPlace, condition: TravelCondition) -> float:
    if not condition.preferred_visit_types:
        return 0.5
    haystack = " ".join(
        part
        for part in (place.title, place.overview or "", " ".join(place.tags))
        if part
    ).lower()
    for preference in condition.preferred_visit_types:
        keywords = VISIT_PREFERENCE_KEYWORDS.get(preference, ())
        if any(keyword.lower() in haystack for keyword in keywords):
            return 1.0
    return 0.2


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))
