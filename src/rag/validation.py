from __future__ import annotations

import re
from typing import Iterable, Mapping, Sequence

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
from .retrieval import haversine_km


DEFAULT_DAY_START = "09:00"
DEFAULT_DAY_END = "20:00"
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
    required_keys = {
        _normalized(value) for value in conditions.must_visit_places
    }
    previous: RetrievedPlace | None = None
    previous_day: int | None = None
    max_leg = _max_leg_distance(conditions)
    for slot_result in sorted(
        slot_candidates,
        key=lambda item: (item.slot.day, item.slot.sequence),
    ):
        if previous_day != slot_result.slot.day:
            previous = None
            previous_day = slot_result.slot.day

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
        place = next(
            (
                item
                for item in ranked
                if item.content_id not in used
                and not _is_excluded(
                    item.title,
                    conditions.excluded_places,
                )
            ),
            None,
        )
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
                reason=(
                    "AIHub 동선 슬롯의 권역·유형과 TourAPI 검색 점수를 "
                    "기준으로 선택했습니다."
                ),
            )
        )
    return ItineraryDraft(tuple(choices))


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
        items.sort(key=lambda item: item[0].slot_sequence)
        current = _time_to_minutes(
            conditions.arrival_time
            if day == 1 and conditions.arrival_time
            else day_start
        )
        day_limit = _time_to_minutes(
            conditions.departure_time
            if day == last_day and conditions.departure_time
            else day_end
        )
        previous: RetrievedPlace | None = None
        for choice, place in items:
            distance = (
                _distance(previous, place) if previous is not None else None
            )
            if distance is not None:
                if distance > max_leg:
                    issues.append(
                        ValidationIssue(
                            "distance_limit",
                            f"{previous.title}에서 {place.title}까지 "
                            f"{distance:.1f}km로 이동거리 제한 "
                            f"{max_leg:.1f}km를 초과함",
                            choice.day,
                            choice.slot_sequence,
                            choice.content_id,
                        )
                    )
                current += max(10, round(distance / speed * 60))

            opening_ranges = parse_opening_ranges(place.opening_hours)
            if opening_ranges:
                start, close = _matching_opening_window(
                    current,
                    choice.stay_minutes,
                    opening_ranges,
                )
                if start is None or close is None:
                    issues.append(
                        ValidationIssue(
                            "outside_opening_hours",
                            f"{place.title}을 운영시간 안에 배치할 수 없음: "
                            f"{place.opening_hours}",
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
                )
            )
            current = end
            previous = place
    return schedule, issues


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


def _matching_opening_window(
    proposed_start: int,
    stay_minutes: int,
    ranges: Iterable[tuple[int, int]],
) -> tuple[int | None, int | None]:
    for opening, closing in ranges:
        start = max(proposed_start, opening)
        if start + stay_minutes <= closing:
            return start, closing
    return None, None


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


def _is_excluded(title: str, excluded_places: Sequence[str]) -> bool:
    normalized_title = _normalized(title)
    return any(
        value and value in normalized_title
        for value in (_normalized(item) for item in excluded_places)
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
