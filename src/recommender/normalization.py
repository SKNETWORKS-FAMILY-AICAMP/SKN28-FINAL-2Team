from __future__ import annotations

from typing import Any

from .models import ItineraryStop, NormalizedItinerary


_TOURISM_ROLES = {"visit", "activity", "tourism", "spot", "attraction", "food", "shopping"}


def normalize_itinerary(payload: dict[str, Any]) -> NormalizedItinerary:
    """Normalize both the current RAG response and the older flat response."""

    if not isinstance(payload, dict):
        raise ValueError("itinerary payload must be an object")
    conditions = payload.get("condition") or payload.get("conditions") or {}
    if not isinstance(conditions, dict):
        raise ValueError("condition(s) must be an object")
    duration = _as_positive_int(conditions.get("duration_days"), "duration_days")
    if duration > 5:
        raise ValueError("duration_days must be between 1 and 5")

    raw_itinerary = payload.get("itinerary")
    stops: list[ItineraryStop] = []
    if isinstance(raw_itinerary, dict):
        for day_row in raw_itinerary.get("days") or []:
            day = _as_positive_int(day_row.get("day"), "day")
            for index, row in enumerate(day_row.get("stops") or [], start=1):
                role = str(row.get("role") or "visit").strip().lower()
                if role not in _TOURISM_ROLES:
                    continue
                stops.append(_to_stop(row, day, index))
    elif isinstance(raw_itinerary, list):
        for index, row in enumerate(raw_itinerary, start=1):
            kind = str(row.get("slot_kind") or row.get("role") or "tourism").lower()
            if kind not in _TOURISM_ROLES:
                continue
            day = _as_positive_int(row.get("day"), "day")
            stops.append(_to_stop(row, day, index))
    else:
        raise ValueError("itinerary must be a days object or a flat list")

    if not stops:
        raise ValueError("itinerary has no tourism stops with content_id")
    if any(stop.day > duration for stop in stops):
        raise ValueError("itinerary stop day exceeds duration_days")
    stops.sort(key=lambda row: (row.day, row.sequence))
    return NormalizedItinerary(duration, dict(conditions), tuple(stops))


def with_place_coordinates(
    itinerary: NormalizedItinerary,
    places: dict[int, dict[str, Any]],
) -> NormalizedItinerary:
    hydrated: list[ItineraryStop] = []
    for stop in itinerary.tourism_stops:
        place = places.get(stop.content_id, {})
        hydrated.append(
            ItineraryStop(
                day=stop.day,
                sequence=stop.sequence,
                content_id=stop.content_id,
                title=stop.title or str(place.get("title") or ""),
                longitude=_optional_float(place.get("longitude")),
                latitude=_optional_float(place.get("latitude")),
            )
        )
    return NormalizedItinerary(
        itinerary.duration_days, itinerary.conditions, tuple(hydrated)
    )


def _to_stop(row: dict[str, Any], day: int, fallback_sequence: int) -> ItineraryStop:
    content_id = _as_positive_int(row.get("content_id"), "content_id")
    sequence = _as_positive_int(row.get("sequence") or fallback_sequence, "sequence")
    return ItineraryStop(
        day=day,
        sequence=sequence,
        content_id=content_id,
        title=str(row.get("title") or ""),
        longitude=_optional_float(row.get("longitude")),
        latitude=_optional_float(row.get("latitude")),
    )


def _as_positive_int(value: Any, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if parsed <= 0:
        raise ValueError(f"{field} must be greater than zero")
    return parsed


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)
