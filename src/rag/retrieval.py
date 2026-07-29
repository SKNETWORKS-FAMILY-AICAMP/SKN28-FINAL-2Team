from __future__ import annotations

from dataclasses import replace
import math
import re
from typing import Any, Mapping, Sequence

from .models import (
    PlaceSearchFilters,
    RetrievedPlace,
    SlotCandidates,
    SlotRequest,
    TravelConditions,
)
from .service import PlaceSearchService


CATEGORY_QUERY_LABELS = {
    "nature": "자연 경관",
    "history": "역사",
    "culture": "문화",
    "market_shopping": "시장과 쇼핑",
    "leisure": "레저",
    "theme_park": "테마파크",
    "trail": "트레일과 산책",
    "festival": "축제",
    "food_cafe": "음식과 카페",
    "experience": "체험",
}
PACE_SLOTS_PER_DAY = {
    "relaxed": 3,
    "balanced": 4,
    "packed": 5,
}
SYNTHETIC_FALLBACK_CATEGORIES = ("nature", "culture", "history")
SYNTHETIC_TARGET_COLLECTIONS = ("attractions",)
SYNTHETIC_ITINERARY_ROLES = ("visit",)
MEAL_SLOT_SEQUENCES = {
    "breakfast": 101,
    "lunch": 102,
    "dinner": 103,
}
MEAL_STAY_MINUTES = {
    "breakfast": 50,
    "lunch": 60,
    "dinner": 70,
}
MEAL_QUERY_LABELS = {
    "breakfast": "아침식사 식당",
    "lunch": "점심식사 식당",
    "dinner": "저녁식사 식당",
}


class SlotRetriever:
    def __init__(
        self,
        place_service: PlaceSearchService,
        *,
        candidates_per_slot: int = 5,
        vector_candidate_multiplier: int = 6,
    ) -> None:
        if candidates_per_slot <= 0 or vector_candidate_multiplier <= 0:
            raise ValueError("slot retrieval limits must be positive")
        self.place_service = place_service
        self.candidates_per_slot = candidates_per_slot
        self.vector_candidate_multiplier = vector_candidate_multiplier

    def retrieve(
        self,
        slot: SlotRequest,
        conditions: TravelConditions,
        *,
        reserved_content_ids: Sequence[int] = (),
    ) -> SlotCandidates:
        query = build_slot_query(slot, conditions)
        response = self.place_service.search_places(
            query,
            filters=PlaceSearchFilters(
                target_collections=slot.target_collections,
                itinerary_roles=slot.itinerary_roles,
                recommendation_scopes=("default",),
                route_eligible=True,
                schedule_eligible=True,
                requires_verification=False,
            ),
            top_k=max(
                self.candidates_per_slot * self.vector_candidate_multiplier,
                20,
            ),
            candidate_k=max(
                self.candidates_per_slot * self.vector_candidate_multiplier,
                30,
            ),
            include_aihub_evidence=False,
        )
        reserved = {int(value) for value in reserved_content_ids}
        excluded = {
            _normalized(value)
            for value in (
                *conditions.excluded_places,
                *conditions.excluded_foods,
            )
        }
        required_keys = {
            _normalized(value)
            for value in required_place_names_for_day(conditions, slot.day)
            if _normalized(value)
        }
        scored: list[RetrievedPlace] = []
        for place in response.places:
            if place.content_id in reserved:
                continue
            if slot.slot_kind == "meal" and not _is_food_or_cafe(place):
                continue
            if slot.slot_kind != "meal" and _is_food_or_cafe(place):
                continue
            if (
                slot.slot_kind == "meal"
                and not _supports_meal_window(
                    place.opening_hours,
                    meal_type=slot.meal_type,
                    stay_minutes=slot.stay_minutes or 60,
                )
            ):
                continue
            if any(
                key
                and key
                in _normalized(
                    " ".join(
                        (
                            place.title,
                            place.overview,
                            *place.tags,
                        )
                    )
                )
                for key in excluded
            ):
                continue
            if conditions.parking_required is True and not _parking_available(
                place.parking
            ):
                continue
            distance = _slot_distance(slot, place)
            normalized_title = _normalized(place.title)
            required_match = any(
                key in normalized_title or normalized_title in key
                for key in required_keys
            )
            if (
                slot.radius_km is not None
                and distance is not None
                and distance > slot.radius_km
                and not required_match
            ):
                continue
            score, breakdown = score_slot_candidate(
                place,
                slot,
                conditions,
                distance_km=distance,
            )
            scored.append(
                replace(
                    place,
                    distance_km=(
                        round(distance, 3) if distance is not None else None
                    ),
                    slot_score=round(score, 6),
                    score_breakdown=breakdown,
                )
            )
        scored.sort(
            key=lambda place: (
                -(place.slot_score or 0.0),
                place.distance_km if place.distance_km is not None else math.inf,
                place.content_id,
            )
        )
        return SlotCandidates(
            slot=slot,
            query=query,
            candidates=tuple(scored[: self.candidates_per_slot]),
        )


def route_slots(
    route_context: Mapping[str, Any],
    *,
    duration_days: int,
    max_slots_per_day: int | None = None,
) -> tuple[SlotRequest, ...]:
    patterns = route_context.get("reference_trip_patterns")
    if not isinstance(patterns, list) or not patterns:
        return ()
    pattern = patterns[0]
    days = pattern.get("days") if isinstance(pattern, Mapping) else None
    if not isinstance(days, list):
        return ()
    slots: list[SlotRequest] = []
    for raw_day in days:
        if not isinstance(raw_day, Mapping):
            continue
        day = int(raw_day.get("day") or 0)
        if not 1 <= day <= duration_days:
            continue
        region = raw_day.get("region")
        center = region.get("center") if isinstance(region, Mapping) else None
        radius = (
            _optional_float(region.get("vector_search_radius_km"))
            if isinstance(region, Mapping)
            else None
        )
        for raw_slot in raw_day.get("slots") or []:
            if not isinstance(raw_slot, Mapping):
                continue
            location = raw_slot.get("location_hint")
            latitude = (
                _optional_float(location.get("latitude"))
                if isinstance(location, Mapping)
                else None
            )
            longitude = (
                _optional_float(location.get("longitude"))
                if isinstance(location, Mapping)
                else None
            )
            if latitude is None and isinstance(center, Mapping):
                latitude = _optional_float(center.get("latitude"))
            if longitude is None and isinstance(center, Mapping):
                longitude = _optional_float(center.get("longitude"))
            collections = tuple(
                str(value) for value in raw_slot.get("target_collections") or ()
            )
            roles = tuple(
                str(value) for value in raw_slot.get("itinerary_roles") or ()
            )
            if not collections or not roles:
                continue
            slots.append(
                SlotRequest(
                    day=day,
                    sequence=int(raw_slot.get("sequence") or len(slots) + 1),
                    role=str(raw_slot.get("role") or "visit"),
                    category=str(raw_slot.get("category") or "unknown"),
                    target_collections=collections,
                    itinerary_roles=roles,
                    stay_minutes=_optional_int(raw_slot.get("stay_minutes")),
                    latitude=latitude,
                    longitude=longitude,
                    radius_km=radius,
                )
            )
    ordered = tuple(sorted(slots, key=lambda slot: (slot.day, slot.sequence)))
    if max_slots_per_day is None:
        return ordered
    if max_slots_per_day <= 0:
        raise ValueError("max_slots_per_day must be positive")
    compacted: list[SlotRequest] = []
    for day in range(1, duration_days + 1):
        day_slots = [slot for slot in ordered if slot.day == day]
        selected = _evenly_spaced_slots(day_slots, max_slots_per_day)
        compacted.extend(
            replace(slot, sequence=sequence)
            for sequence, slot in enumerate(selected, start=1)
        )
    return tuple(compacted)


def complete_route_slots(
    slots: Sequence[SlotRequest],
    conditions: TravelConditions,
    *,
    places_per_day: int,
    anchor_radius_km: float,
) -> tuple[SlotRequest, ...]:
    """Fill missing AIHub day slots around the nearest known route anchor.

    Synthetic slots preserve the historical slots already available. They only
    provide TourAPI retrieval requests and are explicitly marked so they cannot
    be mistaken for observed AIHub visits.
    """

    duration_days = int(conditions.duration_days or 0)
    if duration_days <= 0:
        raise ValueError("duration_days must be positive")
    if places_per_day <= 0:
        raise ValueError("places_per_day must be positive")
    if anchor_radius_km <= 0:
        raise ValueError("anchor_radius_km must be positive")

    raw_ordered = sorted(slots, key=lambda slot: (slot.day, slot.sequence))
    preferred_categories = tuple(
        category
        for category in conditions.preferred_visit_types
        if category != "food_cafe"
    )
    historical_categories = tuple(
        dict.fromkeys(
            slot.category
            for slot in raw_ordered
            if slot.category not in {"", "unknown", "food_cafe"}
        )
    )
    categories = (
        preferred_categories
        or historical_categories
        or SYNTHETIC_FALLBACK_CATEGORIES
    )
    ordered = [
        _retarget_food_slot(slot, categories=categories)
        for slot in raw_ordered
    ]
    by_day = {
        day: [slot for slot in ordered if slot.day == day][:places_per_day]
        for day in range(1, duration_days + 1)
    }

    completed: list[SlotRequest] = []
    previous_anchor: SlotRequest | None = None
    for day in range(1, duration_days + 1):
        existing = list(by_day[day])
        if existing:
            previous_anchor = existing[-1]
        else:
            previous_anchor = _nearest_route_anchor(
                ordered,
                day=day,
                previous=previous_anchor,
            )

        while len(existing) < places_per_day:
            sequence = len(existing) + 1
            anchor = existing[-1] if existing else previous_anchor
            route_anchor = None
            if day == 1 and sequence == 1:
                route_anchor = conditions.entry_point
            if day == duration_days and sequence == places_per_day:
                route_anchor = conditions.exit_point or route_anchor
            category = categories[(sequence - 1) % len(categories)]
            synthetic = SlotRequest(
                day=day,
                sequence=sequence,
                role="visit",
                category=category,
                target_collections=SYNTHETIC_TARGET_COLLECTIONS,
                itinerary_roles=SYNTHETIC_ITINERARY_ROLES,
                stay_minutes=(
                    anchor.stay_minutes
                    if anchor is not None and anchor.stay_minutes is not None
                    else 90
                ),
                latitude=anchor.latitude if anchor is not None else None,
                longitude=anchor.longitude if anchor is not None else None,
                radius_km=min(
                    anchor_radius_km,
                    (
                        anchor.radius_km
                        if anchor is not None and anchor.radius_km is not None
                        else anchor_radius_km
                    ),
                ),
                template_source="synthetic_gap_fill",
                route_anchor=route_anchor,
            )
            existing.append(synthetic)
            previous_anchor = synthetic

        completed.extend(
            replace(slot, sequence=sequence)
            for sequence, slot in enumerate(existing, start=1)
        )
        previous_anchor = existing[-1]
    return tuple(completed)


def tourapi_only_slots(
    conditions: TravelConditions,
    *,
    places_per_day: int,
    radius_km: float,
) -> tuple[SlotRequest, ...]:
    """Create broad TourAPI slots when AIHub has no usable route at all."""

    generated = complete_route_slots(
        (),
        conditions,
        places_per_day=places_per_day,
        anchor_radius_km=radius_km,
    )
    return tuple(
        replace(slot, template_source="tourapi_only_fallback")
        for slot in generated
    )


def add_meal_slots(
    slots: Sequence[SlotRequest],
    conditions: TravelConditions,
    *,
    radius_km: float = 8.0,
) -> tuple[SlotRequest, ...]:
    """Add meal retrieval slots while preserving three tourism slots per day."""

    resolved_radius_km = conditions.meal_search_radius_km or radius_km
    if resolved_radius_km <= 0:
        raise ValueError("radius_km must be positive")
    duration_days = int(conditions.duration_days or 0)
    if duration_days <= 0:
        raise ValueError("duration_days must be positive")

    tourism_slots = [
        slot for slot in slots if slot.slot_kind != "meal"
    ]
    skipped_meals = {
        (item.day, item.meal_type) for item in conditions.skipped_meals
    }
    result = list(tourism_slots)
    for day in range(1, duration_days + 1):
        day_slots = sorted(
            (slot for slot in tourism_slots if slot.day == day),
            key=lambda slot: slot.sequence,
        )
        if not day_slots:
            continue
        meal_types = (
            ("breakfast", "lunch", "dinner")
            if conditions.include_breakfast is True
            else ("lunch", "dinner")
        )
        for meal_type in meal_types:
            if (day, meal_type) in skipped_meals:
                continue
            if meal_type == "breakfast":
                anchor = day_slots[0]
            elif meal_type == "lunch":
                anchor = day_slots[min(1, len(day_slots) - 1)]
            else:
                anchor = day_slots[-1]
            result.append(
                SlotRequest(
                    day=day,
                    sequence=MEAL_SLOT_SEQUENCES[meal_type],
                    role="meal",
                    category="food_cafe",
                    target_collections=("restaurants",),
                    itinerary_roles=("meal", "food"),
                    stay_minutes=MEAL_STAY_MINUTES[meal_type],
                    latitude=anchor.latitude,
                    longitude=anchor.longitude,
                    radius_km=resolved_radius_km,
                    template_source="meal_policy",
                    route_anchor=anchor.route_anchor,
                    slot_kind="meal",
                    meal_type=meal_type,
                )
            )
    return tuple(sorted(result, key=slot_route_order))


def slot_route_order(slot: SlotRequest) -> tuple[int, int]:
    """Return the display/travel order for tourism and meal slots."""

    order = {
        MEAL_SLOT_SEQUENCES["breakfast"]: 10,
        1: 20,
        MEAL_SLOT_SEQUENCES["lunch"]: 30,
        2: 40,
        3: 50,
        MEAL_SLOT_SEQUENCES["dinner"]: 60,
    }
    return slot.day, order.get(slot.sequence, 100 + slot.sequence)


def _nearest_route_anchor(
    slots: Sequence[SlotRequest],
    *,
    day: int,
    previous: SlotRequest | None,
) -> SlotRequest | None:
    if previous is not None and (
        previous.latitude is not None or previous.longitude is not None
    ):
        return previous
    future = [
        slot
        for slot in slots
        if slot.day > day
        and slot.latitude is not None
        and slot.longitude is not None
    ]
    return future[0] if future else previous


def _retarget_food_slot(
    slot: SlotRequest,
    *,
    categories: Sequence[str],
) -> SlotRequest:
    if (
        slot.category != "food_cafe"
        and "restaurants" not in slot.target_collections
        and not {"meal", "cafe_break", "food"}.intersection(
            slot.itinerary_roles
        )
    ):
        return slot
    category = categories[(max(slot.sequence, 1) - 1) % len(categories)]
    return replace(
        slot,
        role="visit",
        category=category,
        target_collections=SYNTHETIC_TARGET_COLLECTIONS,
        itinerary_roles=SYNTHETIC_ITINERARY_ROLES,
        template_source="aihub_food_slot_retarget",
    )


def select_route_context(
    route_context: Mapping[str, Any],
    *,
    duration_days: int,
    pace: str | None,
    max_leg_distance_km: float = 40.0,
    places_per_day: int | None = None,
) -> dict[str, Any]:
    """Put the most usable AIHub pattern first without changing its contents."""

    copied = dict(route_context)
    patterns = route_context.get("reference_trip_patterns")
    if not isinstance(patterns, list):
        return copied
    slots_per_day = places_per_day or PACE_SLOTS_PER_DAY.get(pace or "", 4)
    target_slots = duration_days * slots_per_day

    def rank(
        pattern: Any,
    ) -> tuple[int, int, int, int, int, float, float]:
        if not isinstance(pattern, Mapping):
            return (
                duration_days,
                duration_days,
                target_slots,
                target_slots,
                target_slots,
                math.inf,
                0.0,
            )
        days = pattern.get("days")
        valid_days = {
            int(day.get("day") or 0)
            for day in days or ()
            if isinstance(day, Mapping)
            and 1 <= int(day.get("day") or 0) <= duration_days
        }
        missing = duration_days - len(valid_days)
        compacted = route_slots(
            {"reference_trip_patterns": [pattern]},
            duration_days=duration_days,
            max_slots_per_day=slots_per_day,
        )
        missing_coordinates = 0
        over_limit = 0
        total_distance = 0.0
        for first, second in zip(compacted, compacted[1:]):
            if first.day != second.day:
                continue
            coordinates = (
                first.latitude,
                first.longitude,
                second.latitude,
                second.longitude,
            )
            if any(value is None for value in coordinates):
                missing_coordinates += 1
                continue
            distance = haversine_km(*coordinates)  # type: ignore[arg-type]
            total_distance += distance
            if distance > max_leg_distance_km:
                over_limit += 1
        return (
            missing,
            abs(len(valid_days) - duration_days),
            max(0, target_slots - len(compacted)),
            missing_coordinates,
            over_limit,
            abs(len(compacted) - target_slots) + total_distance / 1000.0,
            -float(pattern.get("match_score") or 0.0),
        )

    copied["reference_trip_patterns"] = sorted(patterns, key=rank)
    return copied


def build_slot_query(
    slot: SlotRequest,
    conditions: TravelConditions,
) -> str:
    if slot.slot_kind == "meal":
        parts = [
            "제주",
            MEAL_QUERY_LABELS.get(slot.meal_type or "", "식당"),
            "가까운 식당",
        ]
        menu_preferences = [
            value
            for value in conditions.preferred_foods
            if _normalized(value)
            not in {"상관없음", "아무거나", "없음", "nopreference"}
        ]
        if menu_preferences:
            parts.append("원하는 메뉴 " + ", ".join(menu_preferences))
        if conditions.excluded_foods:
            parts.append("제외 음식 " + ", ".join(conditions.excluded_foods))
        return ". ".join(parts)

    parts = [
        "제주",
        CATEGORY_QUERY_LABELS.get(slot.category, slot.category),
        " ".join(value.replace("_", " ") for value in slot.itinerary_roles),
    ]
    if conditions.preferred_visit_types:
        parts.append(
            "선호 "
            + ", ".join(
                CATEGORY_QUERY_LABELS.get(value, value)
                for value in conditions.preferred_visit_types
            )
        )
    if conditions.preferred_places:
        parts.append("좋아하는 장소 " + ", ".join(conditions.preferred_places))
    if conditions.preferred_foods:
        parts.append("좋아하는 음식 " + ", ".join(conditions.preferred_foods))
    if conditions.travel_styles:
        parts.append("여행 스타일 " + ", ".join(conditions.travel_styles))
    if conditions.party_type:
        parts.append("동행 " + conditions.party_type)
    if conditions.pace:
        parts.append("여행 속도 " + conditions.pace)
    required_places = required_place_names_for_day(conditions, slot.day)
    if required_places:
        parts.append("필수 " + ", ".join(required_places))
    if slot.template_source in {
        "synthetic_gap_fill",
        "tourapi_only_fallback",
    }:
        parts.append("AIHub 누락 슬롯 보충 관광지")
    if slot.route_anchor:
        parts.append("동선 종료 지점 " + slot.route_anchor)
    if conditions.mobility_constraints:
        parts.append("제약 " + ", ".join(conditions.mobility_constraints))
    if conditions.indoor_preference in {"indoor", "outdoor"}:
        parts.append(
            "실내 장소"
            if conditions.indoor_preference == "indoor"
            else "야외 장소"
        )
    if conditions.parking_required:
        parts.append("주차 가능")
    return ". ".join(part for part in parts if part)


def score_slot_candidate(
    place: RetrievedPlace,
    slot: SlotRequest,
    conditions: TravelConditions,
    *,
    distance_km: float | None,
) -> tuple[float, dict[str, float]]:
    semantic = max(0.0, min(1.0, place.similarity_score))
    if distance_km is None or slot.radius_km in (None, 0):
        geographic = 0.5
    else:
        geographic = max(0.0, 1.0 - distance_km / float(slot.radius_km))
    normalized_tags = " ".join(place.tags).lower()
    category_tokens = {
        slot.category.lower(),
        CATEGORY_QUERY_LABELS.get(slot.category, "").lower(),
    }
    category = (
        1.0
        if any(token and token in normalized_tags for token in category_tokens)
        or place.target_collection in slot.target_collections
        else 0.4
    )
    operations = (
        1.0
        if place.opening_hours and not place.requires_verification
        else 0.5
        if not place.requires_verification
        else 0.0
    )
    if slot.slot_kind == "meal":
        rating = (
            max(0.0, min(1.0, float(place.rating) / 5.0))
            if place.rating is not None
            else 0.5
        )
        menu_terms = tuple(
            value
            for value in conditions.preferred_foods
            if _normalized(value)
            not in {"상관없음", "아무거나", "없음", "nopreference"}
        )
        raw_menu_text = " ".join(
            str(place.raw.get(key) or "")
            for key in (
                "search_text",
                "type_details",
                "first_menu_raw",
                "treat_menu_raw",
            )
        )
        menu_text = _normalized(
            " ".join(
                (place.title, place.overview, *place.tags, raw_menu_text)
            )
        )
        menu_match = (
            1.0
            if menu_terms
            and any(
                _normalized(value) in menu_text
                for value in menu_terms
                if _normalized(value)
            )
            else 0.5
            if not menu_terms
            else 0.0
        )
        breakdown = {
            "geographic": round(geographic, 6),
            "rating": round(rating, 6),
            "menu_match": round(menu_match, 6),
            "semantic": round(semantic, 6),
            "operations": round(operations, 6),
            "rating_available": 1.0 if place.rating is not None else 0.0,
        }
        score = (
            geographic * 0.45
            + rating * 0.25
            + menu_match * 0.15
            + semantic * 0.10
            + operations * 0.05
        )
        return score, breakdown

    normalized_title = _normalized(place.title)
    required = (
        1.0
        if any(
            _normalized(name) in normalized_title
            for name in required_place_names_for_day(conditions, slot.day)
            if _normalized(name)
        )
        else 0.0
    )
    preference_text = _normalized(
        " ".join((place.title, place.overview, *place.tags))
    )
    preference_terms = (
        *conditions.preferred_places,
        *conditions.preferred_foods,
        *conditions.travel_styles,
    )
    preference = (
        1.0
        if any(
            _normalized(value) in preference_text
            for value in preference_terms
            if _normalized(value)
        )
        else 0.0
    )
    breakdown = {
        "semantic": round(semantic, 6),
        "geographic": round(geographic, 6),
        "category": round(category, 6),
        "operations": round(operations, 6),
        "preference": round(preference, 6),
        "required_bonus": round(required, 6),
    }
    score = (
        semantic * 0.40
        + geographic * 0.30
        + category * 0.15
        + operations * 0.10
        + preference * 0.10
        + required * 0.25
    )
    return score, breakdown


def required_place_names_for_day(
    conditions: TravelConditions,
    day: int,
) -> tuple[str, ...]:
    day_specific = tuple(
        name
        for item in conditions.required_day_itineraries
        if item.day == day
        for name in item.place_names
    )
    return tuple(
        dict.fromkeys((*conditions.must_visit_places, *day_specific))
    )


def haversine_km(
    latitude1: float,
    longitude1: float,
    latitude2: float,
    longitude2: float,
) -> float:
    earth_radius = 6371.0088
    delta_latitude = math.radians(latitude2 - latitude1)
    delta_longitude = math.radians(longitude2 - longitude1)
    first = math.radians(latitude1)
    second = math.radians(latitude2)
    value = (
        math.sin(delta_latitude / 2) ** 2
        + math.cos(first)
        * math.cos(second)
        * math.sin(delta_longitude / 2) ** 2
    )
    return earth_radius * 2 * math.asin(math.sqrt(value))


def _slot_distance(
    slot: SlotRequest,
    place: RetrievedPlace,
) -> float | None:
    if (
        slot.latitude is None
        or slot.longitude is None
        or place.latitude == 0.0
        or place.longitude == 0.0
    ):
        return None
    return haversine_km(
        slot.latitude,
        slot.longitude,
        place.latitude,
        place.longitude,
    )


def _normalized(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _parking_available(value: str) -> bool:
    normalized = value.replace(" ", "").lower()
    if not normalized:
        return False
    unavailable = ("불가능", "없음", "주차불가", "no parking")
    return not any(token in normalized for token in unavailable) and any(
        token in normalized
        for token in ("가능", "있음", "주차장", "parking")
    )


def _is_food_or_cafe(place: RetrievedPlace) -> bool:
    if place.target_collection == "restaurants":
        return True
    if place.itinerary_role in {"meal", "cafe_break", "food"}:
        return True
    normalized = _normalized(" ".join(place.tags))
    return any(
        token in normalized
        for token in ("restaurant", "cafe", "음식점", "카페")
    )


def _supports_meal_window(
    opening_hours: str,
    *,
    meal_type: str | None,
    stay_minutes: int,
) -> bool:
    """Reject only explicitly incompatible hours; ambiguous prose is allowed."""

    windows = {
        "breakfast": (7 * 60 + 30, 9 * 60),
        "lunch": (12 * 60, 13 * 60),
        "dinner": (18 * 60, 19 * 60 + 30),
    }
    meal_window = windows.get(meal_type or "")
    if meal_window is None or not opening_hours.strip():
        return True
    normalized = opening_hours.replace("~", "-")
    pattern = re.compile(
        r"(?<!\d)([01]?\d|2[0-3])\s*:\s*([0-5]\d)\s*"
        r"-\s*([01]?\d|2[0-3])\s*:\s*([0-5]\d)"
    )
    ranges = [
        (
            int(match.group(1)) * 60 + int(match.group(2)),
            int(match.group(3)) * 60 + int(match.group(4)),
        )
        for match in pattern.finditer(normalized)
    ]
    if not ranges:
        return True
    window_start, window_end = meal_window
    return any(
        max(opening, window_start) + stay_minutes
        <= min(closing, window_end)
        for opening, closing in ranges
        if closing > opening
    )


def _optional_float(value: Any) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    try:
        return None if value in (None, "") else int(value)
    except (TypeError, ValueError):
        return None


def _evenly_spaced_slots(
    slots: Sequence[SlotRequest],
    limit: int,
) -> tuple[SlotRequest, ...]:
    if len(slots) <= limit:
        return tuple(slots)
    if limit == 1:
        return (slots[len(slots) // 2],)
    indexes = {
        round(position * (len(slots) - 1) / (limit - 1))
        for position in range(limit)
    }
    return tuple(slots[index] for index in sorted(indexes))
