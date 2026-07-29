from __future__ import annotations

import re
from typing import Mapping, Sequence

from .models import (
    ItineraryChoice,
    ItineraryDraft,
    RetrievedPlace,
    ScheduledStop,
    SlotCandidates,
    TravelConditions,
    ValidationIssue,
    ValidationResult,
)
from .retrieval import (
    MEAL_SLOT_SEQUENCES,
    haversine_km,
    required_place_names_for_day,
    slot_route_order,
)


DEFAULT_DAY_START = "09:00"
DEFAULT_DAY_END = "20:00"
VISIT_TYPE_LABELS = {
    "nature": "자연",
    "history": "역사",
    "culture": "문화",
    "market_shopping": "시장·쇼핑",
    "leisure": "레저",
    "theme_park": "테마파크",
    "trail": "트레일",
    "festival": "축제",
    "food_cafe": "음식",
    "experience": "체험",
}
SLOT_TIME_WINDOWS = {
    MEAL_SLOT_SEQUENCES["breakfast"]: (("07:30", "09:00"),),
    1: (("09:00", "12:00"),),
    MEAL_SLOT_SEQUENCES["lunch"]: (("12:00", "13:00"),),
    2: (("13:00", "15:30"),),
    3: (("15:30", "18:00"),),
    MEAL_SLOT_SEQUENCES["dinner"]: (("18:00", "19:30"),),
}
KNOWN_ROUTE_ANCHORS = {
    "제주공항": (33.5104, 126.4913),
    "제주국제공항": (33.5104, 126.4913),
    "제주항": (33.5178, 126.5270),
    "제주항연안여객터미널": (33.5178, 126.5270),
}
TRANSPORT_SPEED_KMH = {
    "rental_car": 38.0,
    "own_car": 38.0,
    "taxi": 38.0,
    "public_transit": 24.0,
    "mixed": 30.0,
}


def validate_and_schedule(
    draft: ItineraryDraft,
    slot_candidates: Sequence[SlotCandidates],
    conditions: TravelConditions,
    *,
    day_start: str = DEFAULT_DAY_START,
    day_end: str = DEFAULT_DAY_END,
) -> ValidationResult:
    slots = {
        (item.slot.day, item.slot.sequence): item for item in slot_candidates
    }
    issues: list[ValidationIssue] = []
    selected: dict[tuple[int, int], tuple[ItineraryChoice, RetrievedPlace]] = {}
    used_ids: set[int] = set()

    for choice in draft.choices:
        key = (choice.day, choice.slot_sequence)
        slot = slots.get(key)
        if slot is None:
            issues.append(
                ValidationIssue(
                    "unknown_slot",
                    f"AIHub 템플릿에 없는 슬롯: Day {choice.day} "
                    f"#{choice.slot_sequence}",
                    choice.day,
                    choice.slot_sequence,
                    choice.content_id,
                )
            )
            continue
        if key in selected:
            issues.append(
                ValidationIssue(
                    "duplicate_slot",
                    f"동일한 슬롯을 두 번 선택함: Day {choice.day} "
                    f"#{choice.slot_sequence}",
                    choice.day,
                    choice.slot_sequence,
                    choice.content_id,
                )
            )
            continue
        allowed = {item.content_id: item for item in slot.candidates}
        place = allowed.get(choice.content_id)
        if place is None:
            issues.append(
                ValidationIssue(
                    "not_whitelisted",
                    f"슬롯 화이트리스트에 없는 TourAPI ID: {choice.content_id}",
                    choice.day,
                    choice.slot_sequence,
                    choice.content_id,
                )
            )
            continue
        if choice.content_id in used_ids:
            issues.append(
                ValidationIssue(
                    "duplicate_place",
                    f"일정에 중복된 TourAPI ID: {choice.content_id}",
                    choice.day,
                    choice.slot_sequence,
                    choice.content_id,
                )
            )
            continue
        if _is_excluded(place.title, conditions.excluded_places):
            issues.append(
                ValidationIssue(
                    "excluded_place",
                    f"사용자 제외 장소가 선택됨: {place.title}",
                    choice.day,
                    choice.slot_sequence,
                    choice.content_id,
                )
            )
            continue
        is_food = _is_food_or_cafe(place)
        if slot.slot.slot_kind == "meal" and not is_food:
            issues.append(
                ValidationIssue(
                    "meal_slot_requires_restaurant",
                    f"식사 슬롯에는 검증된 식당만 선택할 수 있습니다: {place.title}",
                    choice.day,
                    choice.slot_sequence,
                    choice.content_id,
                )
            )
            continue
        if slot.slot.slot_kind != "meal" and is_food:
            issues.append(
                ValidationIssue(
                    "food_or_cafe_not_allowed",
                    f"관광지 일정에 음식점·카페가 선택됨: {place.title}",
                    choice.day,
                    choice.slot_sequence,
                    choice.content_id,
                )
            )
            continue
        selected[key] = (choice, place)
        used_ids.add(choice.content_id)

    missing_slots = sorted(set(slots) - set(selected))
    for day, sequence in missing_slots:
        issues.append(
            ValidationIssue(
                "missing_slot",
                f"선택되지 않은 슬롯: Day {day} #{sequence}",
                day,
                sequence,
            )
        )

    selected_titles = {
        _normalized(place.title) for _, place in selected.values()
    }
    for required_name in conditions.must_visit_places:
        normalized = _normalized(required_name)
        if normalized and not any(
            normalized in title or title in normalized for title in selected_titles
        ):
            issues.append(
                ValidationIssue(
                    "missing_required_place",
                    f"필수 장소가 선택되지 않음: {required_name}",
                )
            )
    selected_titles_by_day: dict[int, set[str]] = {}
    for (day, _), (_, place) in selected.items():
        selected_titles_by_day.setdefault(day, set()).add(
            _normalized(place.title)
        )
    for requirement in conditions.required_day_itineraries:
        day_titles = selected_titles_by_day.get(requirement.day, set())
        for required_name in requirement.place_names:
            normalized = _normalized(required_name)
            if normalized and not any(
                normalized in title or title in normalized
                for title in day_titles
            ):
                issues.append(
                    ValidationIssue(
                        "missing_required_day_place",
                        f"Day {requirement.day} 필수 장소가 선택되지 않음: "
                        f"{required_name}",
                        day=requirement.day,
                    )
                )

    schedule, schedule_issues = _schedule_selected(
        selected,
        conditions,
        day_start=day_start,
        day_end=day_end,
    )
    issues.extend(schedule_issues)
    unique_issues = tuple(_deduplicate_issues(issues))
    return ValidationResult(
        valid=not unique_issues,
        issues=unique_issues,
        schedule=tuple(schedule),
    )


def deterministic_draft(
    slot_candidates: Sequence[SlotCandidates],
    conditions: TravelConditions,
) -> ItineraryDraft:
    """Select the highest-scoring non-duplicate candidate for each slot."""

    used: set[int] = set()
    choices: list[ItineraryChoice] = []
    previous: RetrievedPlace | None = None
    previous_day: int | None = None
    max_leg = _max_leg_distance(conditions)
    ordered_results = sorted(
        slot_candidates,
        key=lambda item: slot_route_order(item.slot),
    )
    for slot_index, slot_result in enumerate(ordered_results):
        if previous_day != slot_result.slot.day:
            previous = None
            previous_day = slot_result.slot.day
        required_keys = {
            _normalized(value)
            for value in required_place_names_for_day(
                conditions,
                slot_result.slot.day,
            )
        }

        def rank_key(place: RetrievedPlace) -> tuple[bool, bool, float, float, int]:
            distance = (
                _distance(previous, place) if previous is not None else None
            )
            return (
                not any(
                    key and key in _normalized(place.title)
                    for key in required_keys
                ),
                distance is not None and distance > max_leg,
                distance if distance is not None else 0.0,
                -(place.slot_score or 0.0),
                place.content_id,
            )

        ranked = sorted(
            slot_result.candidates,
            key=rank_key,
        )
        eligible = [
            item
            for item in ranked
            if item.content_id not in used
            and not _is_excluded(
                item.title,
                conditions.excluded_places,
            )
        ]
        place = next(
            (
                item
                for item in eligible
                if _remaining_slots_have_unique_assignment(
                    ordered_results[slot_index + 1 :],
                    blocked_ids={*used, item.content_id},
                )
            ),
            None,
        )
        if place is None and eligible:
            place = eligible[0]
        if place is None:
            continue
        used.add(place.content_id)
        previous = place
        choices.append(
            ItineraryChoice(
                day=slot_result.slot.day,
                slot_sequence=slot_result.slot.sequence,
                content_id=place.content_id,
                stay_minutes=min(
                    max(slot_result.slot.stay_minutes or 60, 20),
                    360,
                ),
                reason=_deterministic_selection_reason(
                    place,
                    conditions,
                    required_keys=required_keys,
                ),
            )
        )
    return ItineraryDraft(tuple(choices))


def _remaining_slots_have_unique_assignment(
    slots: Sequence[SlotCandidates],
    *,
    blocked_ids: set[int],
) -> bool:
    """Check whether future slots can still receive distinct TourAPI IDs."""

    matched_slot_by_content_id: dict[int, int] = {}

    def assign(slot_index: int, seen: set[int]) -> bool:
        for place in slots[slot_index].candidates:
            content_id = place.content_id
            if content_id in blocked_ids or content_id in seen:
                continue
            seen.add(content_id)
            previous_slot = matched_slot_by_content_id.get(content_id)
            if previous_slot is None or assign(previous_slot, seen):
                matched_slot_by_content_id[content_id] = slot_index
                return True
        return False

    return all(assign(index, set()) for index in range(len(slots)))


def _schedule_selected(
    selected: Mapping[
        tuple[int, int],
        tuple[ItineraryChoice, RetrievedPlace],
    ],
    conditions: TravelConditions,
    *,
    day_start: str,
    day_end: str,
) -> tuple[list[ScheduledStop], list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    schedule: list[ScheduledStop] = []
    grouped: dict[int, list[tuple[ItineraryChoice, RetrievedPlace]]] = {}
    for (day, _), item in selected.items():
        grouped.setdefault(day, []).append(item)

    speed = TRANSPORT_SPEED_KMH.get(
        conditions.local_transport or "mixed",
        30.0,
    )
    max_leg = _max_leg_distance(conditions)
    last_day = conditions.duration_days or max(grouped, default=1)
    for day, items in sorted(grouped.items()):
        items.sort(
            key=lambda item: _sequence_route_order(item[0].slot_sequence)
        )
        effective_day_start = (
            "07:30"
            if conditions.include_breakfast is True
            else day_start
        )
        current = _time_to_minutes(
            conditions.arrival_time
            if day == 1 and conditions.arrival_time
            else effective_day_start
        )
        day_limit = _time_to_minutes(
            conditions.departure_time
            if day == last_day and conditions.departure_time
            else day_end
        )
        previous: RetrievedPlace | None = None
        for choice, place in items:
            previous_label: str | None = None
            if previous is not None:
                distance = _distance(previous, place)
                previous_label = previous.title
            elif day == 1 and conditions.entry_point:
                origin = _known_anchor_coordinates(conditions.entry_point)
                distance = (
                    _distance_from_coordinates(origin, place)
                    if origin is not None
                    else None
                )
                previous_label = conditions.entry_point
            else:
                distance = None
            if distance is not None:
                if distance > max_leg:
                    issues.append(
                        ValidationIssue(
                            "distance_limit",
                            f"{previous_label or '이전 지점'}에서 {place.title}까지 "
                            f"{distance:.1f}km로 이동거리 제한 "
                            f"{max_leg:.1f}km를 초과함",
                            choice.day,
                            choice.slot_sequence,
                            choice.content_id,
                        )
                    )
                current += max(10, round(distance / speed * 60))

            opening_ranges = parse_opening_ranges(place.opening_hours)
            allowed_windows = _slot_windows(
                choice.slot_sequence,
                day_start=(
                    _minutes_to_time(current)
                    if choice.slot_sequence == 1
                    else effective_day_start
                ),
                day_end=_minutes_to_time(day_limit),
            )
            start = _matching_time_slot(
                current,
                choice.stay_minutes,
                opening_ranges,
                allowed_windows,
            )
            if start is None:
                issues.append(
                    ValidationIssue(
                        "outside_time_slot",
                        f"{place.title}을 Day {day} #{choice.slot_sequence} "
                        f"시간대와 운영시간 안에 배치할 수 없음: "
                        f"{place.opening_hours or '운영시간 미확인'}",
                        choice.day,
                        choice.slot_sequence,
                        choice.content_id,
                    )
                )
            else:
                current = start

            end = current + choice.stay_minutes
            if end > day_limit:
                issues.append(
                    ValidationIssue(
                        "day_time_limit",
                        f"{place.title} 종료시각 {_minutes_to_time(end)}이 "
                        f"Day {day} 제한시각 {_minutes_to_time(day_limit)}을 초과함",
                        choice.day,
                        choice.slot_sequence,
                        choice.content_id,
                    )
                )
            schedule.append(
                ScheduledStop(
                    day=day,
                    sequence=choice.slot_sequence,
                    content_id=choice.content_id,
                    title=place.title,
                    start_time=_minutes_to_time(current),
                    end_time=_minutes_to_time(end),
                    stay_minutes=choice.stay_minutes,
                    distance_from_previous_km=(
                        round(distance, 3) if distance is not None else None
                    ),
                    reason=choice.reason,
                    description=_summarize_place(place),
                    slot_kind=(
                        "meal"
                        if choice.slot_sequence
                        in MEAL_SLOT_SEQUENCES.values()
                        else "tourism"
                    ),
                    meal_type=_meal_type(choice.slot_sequence),
                )
            )
            current = end
            previous = place
        if items and day == last_day and conditions.exit_point:
            destination = _known_anchor_coordinates(conditions.exit_point)
            last_choice, last_place = items[-1]
            distance_to_destination = (
                _distance_from_coordinates(destination, last_place)
                if destination is not None
                else None
            )
            if distance_to_destination is not None:
                if distance_to_destination > max_leg:
                    issues.append(
                        ValidationIssue(
                            "destination_distance_limit",
                            f"{last_place.title}에서 {conditions.exit_point}까지 "
                            f"{distance_to_destination:.1f}km로 이동거리 제한 "
                            f"{max_leg:.1f}km를 초과함",
                            last_choice.day,
                            last_choice.slot_sequence,
                            last_choice.content_id,
                        )
                    )
                arrival = current + max(
                    10,
                    round(distance_to_destination / speed * 60),
                )
                if arrival > day_limit:
                    issues.append(
                        ValidationIssue(
                            "destination_time_limit",
                            f"{last_place.title}에서 {conditions.exit_point} "
                            f"도착시각 {_minutes_to_time(arrival)}이 제한시각 "
                            f"{_minutes_to_time(day_limit)}을 초과함",
                            last_choice.day,
                            last_choice.slot_sequence,
                            last_choice.content_id,
                        )
                    )
    return schedule, issues


def _summarize_place(place: RetrievedPlace, *, max_length: int = 180) -> str:
    """Return a factual one-to-two sentence TourAPI summary."""

    overview = re.sub(r"\s+", " ", place.overview or "").strip()
    if overview:
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", overview)
            if sentence.strip()
        ]
        summary = " ".join(sentences[:2]) if sentences else overview
    elif place.address:
        summary = f"{place.address}에 위치한 {place.title}입니다."
    else:
        summary = f"TourAPI에 등록된 제주 장소인 {place.title}입니다."

    if len(summary) <= max_length:
        return summary
    shortened = summary[: max_length - 1].rsplit(" ", 1)[0].rstrip(" ,.")
    return (shortened or summary[: max_length - 1]).rstrip() + "…"


def _deterministic_selection_reason(
    place: RetrievedPlace,
    conditions: TravelConditions,
    *,
    required_keys: set[str],
) -> str:
    """Explain the fallback choice using only verified scoring inputs."""

    title = _normalized(place.title)
    if any(key and key in title for key in required_keys):
        return "사용자가 지정한 필수 방문 장소이므로 우선 배치했습니다."

    factors: list[str] = []
    if place.target_collection == "restaurants":
        if conditions.preferred_foods:
            factors.append("선호 메뉴")
        if place.rating is not None:
            factors.append(f"평점 {place.rating:.1f}")
    elif conditions.preferred_visit_types:
        labels = [
            VISIT_TYPE_LABELS.get(value, value)
            for value in conditions.preferred_visit_types[:2]
        ]
        factors.append("·".join(labels) + " 선호")
    if place.distance_km is not None:
        factors.append(f"검색 기준 위치에서 {place.distance_km:.1f}km")
    if conditions.parking_required is True and place.parking:
        factors.append("주차 조건")
    if place.opening_hours:
        factors.append("운영시간 정보")
    if not factors:
        factors.append("TourAPI 자연어 유사도와 동선 적합도")
    return "다음 조건을 반영해 선택했습니다: " + ", ".join(factors[:3]) + "."


def parse_opening_ranges(value: str) -> tuple[tuple[int, int], ...]:
    """Extract explicit HH:MM-HH:MM ranges; ambiguous prose stays unverified."""

    if not value.strip():
        return ()
    normalized = (
        value.replace("~", "-")
        .replace("∼", "-")
        .replace("–", "-")
        .replace("—", "-")
    )
    ranges: list[tuple[int, int]] = []
    pattern = re.compile(
        r"(?<!\d)([01]?\d|2[0-3])\s*[:시]\s*([0-5]\d)?\s*"
        r"-\s*([01]?\d|2[0-3])\s*[:시]\s*([0-5]\d)?"
    )
    for match in pattern.finditer(normalized):
        start = int(match.group(1)) * 60 + int(match.group(2) or 0)
        end = int(match.group(3)) * 60 + int(match.group(4) or 0)
        if end > start:
            ranges.append((start, end))
    return tuple(dict.fromkeys(ranges))


def _matching_time_slot(
    proposed_start: int,
    stay_minutes: int,
    opening_ranges: Sequence[tuple[int, int]],
    allowed_windows: Sequence[tuple[int, int]],
) -> int | None:
    for window_start, window_end in allowed_windows:
        start = max(proposed_start, window_start)
        if opening_ranges:
            for opening, closing in opening_ranges:
                candidate = max(start, opening)
                if candidate + stay_minutes <= min(window_end, closing):
                    return candidate
        elif start + stay_minutes <= window_end:
            return start
    return None


def _slot_windows(
    sequence: int,
    *,
    day_start: str,
    day_end: str,
) -> tuple[tuple[int, int], ...]:
    lower = _time_to_minutes(day_start)
    upper = _time_to_minutes(day_end)
    configured = SLOT_TIME_WINDOWS.get(
        sequence,
        ((day_start, day_end),),
    )
    windows: list[tuple[int, int]] = []
    for start_text, end_text in configured:
        start = max(lower, _time_to_minutes(start_text))
        end = min(upper, _time_to_minutes(end_text))
        if end > start:
            windows.append((start, end))
    return tuple(windows)


def _sequence_route_order(sequence: int) -> int:
    order = {
        MEAL_SLOT_SEQUENCES["breakfast"]: 10,
        1: 20,
        MEAL_SLOT_SEQUENCES["lunch"]: 30,
        2: 40,
        3: 50,
        MEAL_SLOT_SEQUENCES["dinner"]: 60,
    }
    return order.get(sequence, 100 + sequence)


def _meal_type(sequence: int) -> str | None:
    return next(
        (
            meal_type
            for meal_type, meal_sequence in MEAL_SLOT_SEQUENCES.items()
            if meal_sequence == sequence
        ),
        None,
    )


def _max_leg_distance(conditions: TravelConditions) -> float:
    text = " ".join(conditions.mobility_constraints)
    if conditions.avoid_long_distance is True or any(
        keyword in text for keyword in ("긴 이동", "장거리", "이동 최소")
    ):
        return 20.0
    if conditions.local_transport == "public_transit":
        return 25.0
    return 40.0


def max_leg_distance_km(conditions: TravelConditions) -> float:
    """Public prompt/validator contract for the consecutive-leg limit."""

    return _max_leg_distance(conditions)


def _distance(
    first: RetrievedPlace,
    second: RetrievedPlace,
) -> float | None:
    if (
        first.latitude == 0.0
        or first.longitude == 0.0
        or second.latitude == 0.0
        or second.longitude == 0.0
    ):
        return None
    return haversine_km(
        first.latitude,
        first.longitude,
        second.latitude,
        second.longitude,
    )


def _distance_from_coordinates(
    coordinates: tuple[float, float],
    place: RetrievedPlace,
) -> float | None:
    latitude, longitude = coordinates
    if place.latitude == 0.0 or place.longitude == 0.0:
        return None
    return haversine_km(
        latitude,
        longitude,
        place.latitude,
        place.longitude,
    )


def _known_anchor_coordinates(value: str) -> tuple[float, float] | None:
    normalized = _normalized(value)
    for name, coordinates in KNOWN_ROUTE_ANCHORS.items():
        normalized_name = _normalized(name)
        if normalized_name in normalized or normalized in normalized_name:
            return coordinates
    return None


def _is_excluded(title: str, excluded_places: Sequence[str]) -> bool:
    normalized_title = _normalized(title)
    return any(
        value and value in normalized_title
        for value in (_normalized(item) for item in excluded_places)
    )


def _is_food_or_cafe(place: RetrievedPlace) -> bool:
    if place.target_collection == "restaurants":
        return True
    if place.itinerary_role in {"meal", "cafe_break", "food"}:
        return True
    normalized = _normalized(" ".join((place.title, *place.tags)))
    return any(
        token in normalized
        for token in ("restaurant", "cafe", "음식점", "카페")
    )


def _normalized(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _time_to_minutes(value: str) -> int:
    match = re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", value.strip())
    if not match:
        raise ValueError(f"invalid HH:MM time: {value}")
    return int(match.group(1)) * 60 + int(match.group(2))


def _minutes_to_time(value: int) -> str:
    bounded = max(0, min(value, 24 * 60 - 1))
    return f"{bounded // 60:02d}:{bounded % 60:02d}"


def _deduplicate_issues(
    issues: Sequence[ValidationIssue],
) -> list[ValidationIssue]:
    result: list[ValidationIssue] = []
    seen: set[tuple] = set()
    for issue in issues:
        key = (
            issue.code,
            issue.message,
            issue.day,
            issue.slot_sequence,
            issue.content_id,
        )
        if key not in seen:
            result.append(issue)
            seen.add(key)
    return result
