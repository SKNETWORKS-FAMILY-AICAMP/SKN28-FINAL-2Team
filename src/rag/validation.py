from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import json
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
    required_content_ids_for_day,
    required_place_names_for_day,
)
from .routing import (
    HaversineRouteMetricsProvider,
    RouteEstimate,
    RouteMetricsProvider,
)
from .operations import (
    HolidayCalendar,
    OperationalFacts,
    OperationalFactsError,
    PlaceOperationalFactsProvider,
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
WEEKDAY_TOKENS = {
    0: ("월요일", "월요", "매주월", "월요일마다"),
    1: ("화요일", "화요", "매주화", "화요일마다"),
    2: ("수요일", "수요", "매주수", "수요일마다"),
    3: ("목요일", "목요", "매주목", "목요일마다"),
    4: ("금요일", "금요", "매주금", "금요일마다"),
    5: ("토요일", "토요", "매주토", "토요일마다"),
    6: ("일요일", "일요", "매주일", "일요일마다"),
}


@dataclass(frozen=True)
class ValidationPolicy:
    """Controls whether unverifiable facts block or label the draft."""

    block_missing_coordinates: bool = False
    block_missing_opening_hours: bool = False
    block_unverified_routes: bool = False
    block_unknown_anchors: bool = False


def validate_and_schedule(
    draft: ItineraryDraft,
    slot_candidates: Sequence[SlotCandidates],
    conditions: TravelConditions,
    *,
    day_start: str = DEFAULT_DAY_START,
    day_end: str = DEFAULT_DAY_END,
    route_provider: RouteMetricsProvider | None = None,
    policy: ValidationPolicy | None = None,
    operational_provider: PlaceOperationalFactsProvider | None = None,
    holiday_calendar: HolidayCalendar | None = None,
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
    selected_ids = {
        place.content_id for _, place in selected.values()
    }
    for required_id in conditions.must_visit_content_ids:
        if required_id not in selected_ids:
            issues.append(
                ValidationIssue(
                    "missing_required_content_id",
                    f"필수 TourAPI ID가 선택되지 않음: {required_id}",
                    content_id=required_id,
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
        day_ids = {
            place.content_id
            for (selected_day, _), (_, place) in selected.items()
            if selected_day == requirement.day
        }
        for required_id in requirement.content_ids:
            if required_id not in day_ids:
                issues.append(
                    ValidationIssue(
                        "missing_required_day_content_id",
                        f"Day {requirement.day} 필수 TourAPI ID가 선택되지 "
                        f"않음: {required_id}",
                        day=requirement.day,
                        content_id=required_id,
                    )
                )

    schedule, schedule_issues, schedule_warnings = _schedule_selected(
        selected,
        conditions,
        day_start=day_start,
        day_end=day_end,
        route_provider=route_provider or HaversineRouteMetricsProvider(),
        policy=policy or ValidationPolicy(),
        operational_provider=operational_provider,
        holiday_calendar=holiday_calendar,
    )
    issues.extend(schedule_issues)
    schedule_warnings.extend(_condition_support_warnings(conditions))
    unique_issues = tuple(_deduplicate_issues(issues))
    unique_warnings = tuple(_deduplicate_issues(schedule_warnings))
    return ValidationResult(
        valid=not unique_issues,
        issues=unique_issues,
        schedule=tuple(schedule),
        warnings=unique_warnings,
    )


def deterministic_draft(
    slot_candidates: Sequence[SlotCandidates],
    conditions: TravelConditions,
) -> ItineraryDraft:
    """Optimize all candidates per day instead of choosing each slot greedily."""

    grouped: dict[int, list[SlotCandidates]] = {}
    for item in slot_candidates:
        grouped.setdefault(item.slot.day, []).append(item)

    used_ids: set[int] = set()
    choices: list[ItineraryChoice] = []
    for day in sorted(grouped):
        day_results = sorted(
            grouped[day],
            key=lambda item: _dynamic_slot_order(
                item.slot.sequence,
                _tourism_slot_count(grouped[day]),
            ),
        )
        optimized = _optimize_day_candidates(
            day_results,
            conditions,
            blocked_ids=used_ids,
        )
        for slot_result, place in optimized:
            required_keys = {
                _normalized(value)
                for value in required_place_names_for_day(
                    conditions,
                    slot_result.slot.day,
                )
            }
            required_ids = set(
                required_content_ids_for_day(
                    conditions,
                    slot_result.slot.day,
                )
            )
            used_ids.add(place.content_id)
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
                        required_ids=required_ids,
                    ),
                )
            )
    return ItineraryDraft(tuple(choices))


def _optimize_day_candidates(
    slots: Sequence[SlotCandidates],
    conditions: TravelConditions,
    *,
    blocked_ids: set[int],
    beam_width: int = 512,
) -> tuple[tuple[SlotCandidates, RetrievedPlace], ...]:
    """Beam-search a complete, unique assignment with route-aware scoring."""

    # (cost, id_tiebreaker, used_ids, previous_place, assignments)
    states: list[
        tuple[
            float,
            tuple[int, ...],
            frozenset[int],
            RetrievedPlace | None,
            tuple[tuple[SlotCandidates, RetrievedPlace], ...],
        ]
    ] = [(0.0, (), frozenset(blocked_ids), None, ())]
    max_leg = _max_leg_distance(conditions)
    required_keys = {
        _normalized(value)
        for value in required_place_names_for_day(
            conditions,
            slots[0].slot.day if slots else 0,
        )
        if _normalized(value)
    }
    required_ids = set(
        required_content_ids_for_day(
            conditions,
            slots[0].slot.day if slots else 0,
        )
    )

    for slot_result in slots:
        expanded = []
        for cost, tie, used, previous, assignments in states:
            for place in slot_result.candidates:
                if place.content_id in used or _is_excluded(
                    place.title,
                    conditions.excluded_places,
                ):
                    continue
                distance = (
                    _distance(previous, place)
                    if previous is not None
                    else None
                )
                required_match = place.content_id in required_ids or any(
                    key in _normalized(place.title)
                    or _normalized(place.title) in key
                    for key in required_keys
                )
                leg_penalty = (
                    100.0
                    if distance is not None and distance > max_leg
                    else (distance or 0.0) * 0.03
                )
                unknown_coordinate_penalty = 1.0 if distance is None else 0.0
                candidate_cost = (
                    cost
                    + leg_penalty
                    + unknown_coordinate_penalty
                    - float(place.slot_score or 0.0) * 10.0
                    - (25.0 if required_match else 0.0)
                )
                expanded.append(
                    (
                        candidate_cost,
                        (*tie, place.content_id),
                        frozenset((*used, place.content_id)),
                        place,
                        (*assignments, (slot_result, place)),
                    )
                )
        if not expanded:
            return ()
        expanded.sort(key=lambda state: (state[0], state[1]))
        states = expanded[:beam_width]
    return states[0][4] if states else ()


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
    route_provider: RouteMetricsProvider,
    policy: ValidationPolicy,
    operational_provider: PlaceOperationalFactsProvider | None,
    holiday_calendar: HolidayCalendar | None,
) -> tuple[
    list[ScheduledStop],
    list[ValidationIssue],
    list[ValidationIssue],
]:
    issues: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    schedule: list[ScheduledStop] = []
    grouped: dict[int, list[tuple[ItineraryChoice, RetrievedPlace]]] = {}
    for (day, _), item in selected.items():
        grouped.setdefault(day, []).append(item)

    max_leg = _max_leg_distance(conditions)
    last_day = conditions.duration_days or max(grouped, default=1)
    for day, items in sorted(grouped.items()):
        tourism_count = len(
            [
                item
                for item in items
                if item[0].slot_sequence
                not in MEAL_SLOT_SEQUENCES.values()
            ]
        )
        items.sort(
            key=lambda item: _dynamic_slot_order(
                item[0].slot_sequence,
                tourism_count,
            )
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
        start_anchor_name, start_anchor = _day_start_anchor(
            conditions,
            day=day,
        )
        for choice, place in items:
            previous_label: str | None = None
            route: RouteEstimate | None = None
            if previous is not None:
                previous_label = previous.title
                origin = _place_coordinates(previous)
            elif start_anchor_name:
                previous_label = start_anchor_name
                origin = start_anchor
            else:
                origin = None
            destination = _place_coordinates(place)
            if origin is not None and destination is not None:
                route = route_provider.estimate(
                    origin,
                    destination,
                    transport=conditions.local_transport or "mixed",
                )
                if route.distance_km > max_leg:
                    issues.append(
                        ValidationIssue(
                            "distance_limit",
                            f"{previous_label or '이전 지점'}에서 {place.title}까지 "
                            f"{route.distance_km:.1f}km로 이동거리 제한 "
                            f"{max_leg:.1f}km를 초과함",
                            choice.day,
                            choice.slot_sequence,
                            choice.content_id,
                        )
                    )
                current += route.duration_minutes
                if not route.verified:
                    _record_verification_problem(
                        issues,
                        warnings,
                        policy.block_unverified_routes,
                        ValidationIssue(
                            "unverified_route",
                            f"{previous_label or '이전 지점'}에서 {place.title}까지 "
                            "실제 도로 경로가 아닌 직선거리 기반 추정값입니다.",
                            choice.day,
                            choice.slot_sequence,
                            choice.content_id,
                        ),
                    )
            else:
                missing_label = previous_label or place.title
                _record_verification_problem(
                    issues,
                    warnings,
                    policy.block_missing_coordinates,
                    ValidationIssue(
                        "missing_route_coordinates",
                        f"{missing_label} 경로의 좌표를 확인할 수 없습니다.",
                        choice.day,
                        choice.slot_sequence,
                        choice.content_id,
                    ),
                )

            travel_day = _travel_date(conditions.start_date, day)
            facts: OperationalFacts | None = None
            if travel_day is not None and operational_provider is not None:
                try:
                    facts = operational_provider.facts_for(place, travel_day)
                except OperationalFactsError as exc:
                    warnings.append(
                        ValidationIssue(
                            "operational_facts_unavailable",
                            f"{place.title}의 외부 운영정보를 조회하지 못했습니다: "
                            f"{exc}",
                            choice.day,
                            choice.slot_sequence,
                            choice.content_id,
                        )
                    )
            opening_ranges = (
                facts.opening_ranges
                if facts is not None and facts.opening_ranges
                else parse_opening_ranges(place.opening_hours)
            )
            if facts is not None and (
                facts.closed_on_date is True
                or facts.business_status
                in {"CLOSED_TEMPORARILY", "CLOSED_PERMANENTLY"}
            ):
                issues.append(
                    ValidationIssue(
                        "external_closure",
                        f"{place.title}은 {travel_day.isoformat()} 기준 "
                        f"{facts.source}에서 휴무 또는 영업 종료로 확인됩니다.",
                        choice.day,
                        choice.slot_sequence,
                        choice.content_id,
                    )
                )
            if travel_day is not None and is_closed_on_date(
                place.closed_days,
                travel_day,
            ):
                issues.append(
                    ValidationIssue(
                        "closed_on_travel_date",
                        f"{place.title}은 {travel_day.isoformat()} 휴무입니다: "
                        f"{place.closed_days}",
                        choice.day,
                        choice.slot_sequence,
                        choice.content_id,
                    )
                )
            if travel_day is not None and holiday_calendar is not None:
                holiday_name = holiday_calendar.holiday_name(travel_day)
                if holiday_name and not (
                    facts is not None
                    and facts.verified
                    and (
                        facts.opening_ranges
                        or facts.closed_on_date is not None
                    )
                ):
                    warnings.append(
                        ValidationIssue(
                            "holiday_hours_unverified",
                            f"{travel_day.isoformat()}은 {holiday_name}입니다. "
                            f"{place.title}의 공휴일 특별 운영시간 확인이 필요합니다.",
                            choice.day,
                            choice.slot_sequence,
                            choice.content_id,
                        )
                    )
            accessibility_issues, accessibility_warnings = (
                _validate_accessibility(
                    place,
                    facts,
                    conditions,
                    day=choice.day,
                    slot_sequence=choice.slot_sequence,
                )
            )
            issues.extend(accessibility_issues)
            warnings.extend(accessibility_warnings)
            if not opening_ranges:
                _record_verification_problem(
                    issues,
                    warnings,
                    policy.block_missing_opening_hours,
                    ValidationIssue(
                        "opening_hours_unverified",
                        f"{place.title}의 구조화된 운영시간을 확인할 수 없습니다.",
                        choice.day,
                        choice.slot_sequence,
                        choice.content_id,
                    ),
                )
            allowed_windows = _slot_windows(
                choice.slot_sequence,
                tourism_count=tourism_count,
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
                        round(route.distance_km, 3)
                        if route is not None
                        else None
                    ),
                    travel_minutes_from_previous=(
                        route.duration_minutes if route is not None else None
                    ),
                    route_source=route.provider if route is not None else None,
                    route_verified=route.verified if route is not None else False,
                    reason=_selection_reason(
                        place,
                        conditions,
                        day=choice.day,
                    ),
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
        end_anchor_name, end_anchor = _day_end_anchor(
            conditions,
            day=day,
            last_day=last_day,
        )
        if items and end_anchor_name:
            last_choice, last_place = items[-1]
            origin = _place_coordinates(last_place)
            if origin is not None and end_anchor is not None:
                return_route = route_provider.estimate(
                    origin,
                    end_anchor,
                    transport=conditions.local_transport or "mixed",
                )
                if return_route.distance_km > max_leg:
                    issues.append(
                        ValidationIssue(
                            "destination_distance_limit",
                            f"{last_place.title}에서 {end_anchor_name}까지 "
                            f"{return_route.distance_km:.1f}km로 이동거리 제한 "
                            f"{max_leg:.1f}km를 초과함",
                            last_choice.day,
                            last_choice.slot_sequence,
                            last_choice.content_id,
                        )
                    )
                arrival = current + return_route.duration_minutes
                if arrival > day_limit:
                    issues.append(
                        ValidationIssue(
                            "destination_time_limit",
                            f"{last_place.title}에서 {end_anchor_name} "
                            f"도착시각 {_minutes_to_time(arrival)}이 제한시각 "
                            f"{_minutes_to_time(day_limit)}을 초과함",
                            last_choice.day,
                            last_choice.slot_sequence,
                            last_choice.content_id,
                        )
                    )
                if not return_route.verified:
                    _record_verification_problem(
                        issues,
                        warnings,
                        policy.block_unverified_routes,
                        ValidationIssue(
                            "unverified_return_route",
                            f"{last_place.title}에서 {end_anchor_name}까지 실제 "
                            "도로 경로가 아닌 직선거리 기반 추정값입니다.",
                            last_choice.day,
                            last_choice.slot_sequence,
                            last_choice.content_id,
                        ),
                    )
            else:
                _record_verification_problem(
                    issues,
                    warnings,
                    policy.block_unknown_anchors,
                    ValidationIssue(
                        "unknown_route_anchor",
                        f"{end_anchor_name}의 좌표를 확인할 수 없어 복귀 동선을 "
                        "검증하지 못했습니다.",
                        last_choice.day,
                        last_choice.slot_sequence,
                        last_choice.content_id,
                    ),
                )
    return schedule, issues, warnings


def _summarize_place(place: RetrievedPlace, *, max_length: int = 160) -> str:
    """Return a factual one-to-three sentence introduction for the UI."""

    overview = re.sub(r"<[^>]+>", " ", place.overview or "")
    overview = re.sub(r"\s+", " ", overview).strip()
    if overview:
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", overview)
            if sentence.strip()
        ]
        summary = " ".join(sentences[:2]) if sentences else overview
    elif place.address:
        if place.target_collection == "restaurants":
            summary = (
                f"{place.address}에 있는 음식점입니다. "
                "메뉴와 운영정보는 방문 전에 한 번 더 확인해 주세요."
            )
        else:
            category = _place_category_text(place)
            summary = (
                f"{place.address}에 위치한 "
                f"{category + ' ' if category else ''}관광지입니다."
            )
    else:
        category = _place_category_text(place)
        summary = (
            f"{place.title}은 제주 지역의 "
            f"{category + ' ' if category else ''}장소입니다."
        )

    if len(summary) <= max_length:
        return summary
    shortened = summary[: max_length - 1].rsplit(" ", 1)[0].rstrip(" ,.")
    return (shortened or summary[: max_length - 1]).rstrip() + "…"


def _selection_reason(
    place: RetrievedPlace,
    conditions: TravelConditions,
    *,
    day: int,
) -> str:
    """Build a place-specific reason from verified candidate attributes."""

    required_ids = set(required_content_ids_for_day(conditions, day))
    required_names = {
        _normalized(value)
        for value in required_place_names_for_day(conditions, day)
        if _normalized(value)
    }
    normalized_title = _normalized(place.title)
    if place.content_id in required_ids or any(
        key in normalized_title or normalized_title in key
        for key in required_names
    ):
        return (
            f"{place.title}: 사용자가 지정한 필수 방문 장소이므로 "
            f"Day {day} 일정에 우선 배치했습니다."
        )

    facts: list[str] = []
    searchable = _normalized(
        " ".join((place.title, place.overview, *place.tags))
    )
    if place.target_collection == "restaurants":
        menu_matches = [
            value
            for value in conditions.preferred_foods
            if _normalized(value)
            not in {"", "상관없음", "아무거나", "없음", "nopreference"}
            and _normalized(value) in searchable
        ]
        if menu_matches:
            facts.append("·".join(menu_matches[:2]) + " 메뉴 선호 반영")
        if place.rating is not None:
            facts.append(f"확인된 평점 {place.rating:.1f}")
        if place.distance_km is not None:
            facts.append(f"직전 관광지 기준 {place.distance_km:.1f}km")
        if place.opening_hours:
            facts.append("식사 시간대 운영정보 확인")
        if not facts:
            facts.append("선택 관광지 주변의 식사 동선")
        return (
            f"{place.title}: " + ", ".join(facts[:3])
            + " 등의 요소를 고려해 식사 장소로 선택했습니다."
        )

    if conditions.preferred_visit_types:
        labels = [
            VISIT_TYPE_LABELS.get(value, value)
            for value in conditions.preferred_visit_types[:2]
        ]
        if labels:
            facts.append("·".join(labels) + " 선호")
    preferred_matches = [
        value
        for value in (*conditions.preferred_places, *conditions.travel_styles)
        if _normalized(value) and _normalized(value) in searchable
    ]
    if preferred_matches:
        facts.append("·".join(preferred_matches[:2]) + " 취향")
    if place.distance_km is not None:
        facts.append(f"일정 기준 위치에서 {place.distance_km:.1f}km")
    if conditions.parking_required is True and place.parking:
        facts.append("주차 조건")
    if place.opening_hours:
        facts.append("운영시간 정보")
    if not facts:
        category = _place_category_text(place)
        facts.append(
            f"{category} 성격과 해당 일차의 이동 동선"
            if category
            else "해당 일차의 권역과 이동 동선"
        )
    return (
        f"{place.title}: " + ", ".join(facts[:3])
        + " 등의 요소를 고려해 방문 장소로 선택했습니다."
    )


def _place_category_text(place: RetrievedPlace) -> str:
    labels = [
        str(tag).strip()
        for tag in place.tags
        if ":" not in str(tag)
        and str(tag).strip()
        and len(str(tag).strip()) <= 18
    ]
    return "·".join(dict.fromkeys(labels[:2]))


def _deterministic_selection_reason(
    place: RetrievedPlace,
    conditions: TravelConditions,
    *,
    required_keys: set[str],
    required_ids: set[int] | None = None,
) -> str:
    """Explain the fallback choice using only verified scoring inputs."""

    title = _normalized(place.title)
    if place.content_id in (required_ids or set()) or any(
        key and key in title for key in required_keys
    ):
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


def is_closed_on_date(value: str, travel_date: date) -> bool:
    """Recognize explicit dates and common Korean weekly-closure phrases."""

    normalized = re.sub(r"\s+", "", value or "")
    if not normalized or any(
        token in normalized for token in ("연중무휴", "휴무없음", "무휴")
    ):
        return False
    iso = travel_date.isoformat()
    compact = travel_date.strftime("%Y%m%d")
    dotted = travel_date.strftime("%Y.%m.%d")
    slashed = travel_date.strftime("%Y/%m/%d")
    if any(token in normalized for token in (iso, compact, dotted, slashed)):
        return True
    return any(
        token.replace(" ", "") in normalized
        for token in WEEKDAY_TOKENS[travel_date.weekday()]
    )


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
    tourism_count: int,
    day_start: str,
    day_end: str,
) -> tuple[tuple[int, int], ...]:
    lower = _time_to_minutes(day_start)
    upper = _time_to_minutes(day_end)
    if sequence in MEAL_SLOT_SEQUENCES.values():
        configured = SLOT_TIME_WINDOWS.get(sequence, ((day_start, day_end),))
    elif tourism_count <= 3:
        configured = SLOT_TIME_WINDOWS.get(sequence, ((day_start, day_end),))
    else:
        morning_count = max(1, round(tourism_count * 0.4))
        if sequence <= morning_count:
            dynamic_start = 9 * 60 + (sequence - 1) * 90
            dynamic_end = 12 * 60
        else:
            afternoon_index = sequence - morning_count - 1
            afternoon_count = tourism_count - morning_count
            segment = max(75, 5 * 60 // max(afternoon_count, 1))
            dynamic_start = 13 * 60 + afternoon_index * segment
            dynamic_end = min(18 * 60, dynamic_start + segment + 45)
        configured = (
            (
                _minutes_to_time(dynamic_start),
                _minutes_to_time(dynamic_end),
            ),
        )
    windows: list[tuple[int, int]] = []
    for start_text, end_text in configured:
        start = max(lower, _time_to_minutes(start_text))
        end = min(upper, _time_to_minutes(end_text))
        if end > start:
            windows.append((start, end))
    return tuple(windows)


def _dynamic_slot_order(sequence: int, tourism_count: int) -> int:
    if sequence == MEAL_SLOT_SEQUENCES["breakfast"]:
        return 10
    lunch_after = max(1, round(tourism_count * 0.4))
    if sequence == MEAL_SLOT_SEQUENCES["lunch"]:
        return lunch_after * 20 + 10
    if sequence == MEAL_SLOT_SEQUENCES["dinner"]:
        return tourism_count * 20 + 10
    return sequence * 20


def _tourism_slot_count(slots: Sequence[SlotCandidates]) -> int:
    return len(
        [
            item
            for item in slots
            if item.slot.sequence not in MEAL_SLOT_SEQUENCES.values()
        ]
    )


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


def _explicit_coordinates(
    latitude: float | None,
    longitude: float | None,
) -> tuple[float, float] | None:
    if latitude is None or longitude is None:
        return None
    if latitude == 0.0 or longitude == 0.0:
        return None
    return latitude, longitude


def _day_start_anchor(
    conditions: TravelConditions,
    *,
    day: int,
) -> tuple[str | None, tuple[float, float] | None]:
    if day == 1 and conditions.entry_point:
        return (
            conditions.entry_point,
            _explicit_coordinates(
                conditions.entry_latitude,
                conditions.entry_longitude,
            )
            or _known_anchor_coordinates(conditions.entry_point),
        )
    if conditions.accommodation_address:
        return (
            conditions.accommodation_address,
            _explicit_coordinates(
                conditions.accommodation_latitude,
                conditions.accommodation_longitude,
            )
            or _known_anchor_coordinates(conditions.accommodation_address),
        )
    return None, None


def _day_end_anchor(
    conditions: TravelConditions,
    *,
    day: int,
    last_day: int,
) -> tuple[str | None, tuple[float, float] | None]:
    if day == last_day and conditions.exit_point:
        return (
            conditions.exit_point,
            _explicit_coordinates(
                conditions.exit_latitude,
                conditions.exit_longitude,
            )
            or _known_anchor_coordinates(conditions.exit_point),
        )
    if conditions.accommodation_address:
        return (
            conditions.accommodation_address,
            _explicit_coordinates(
                conditions.accommodation_latitude,
                conditions.accommodation_longitude,
            )
            or _known_anchor_coordinates(conditions.accommodation_address),
        )
    return None, None


def _place_coordinates(
    place: RetrievedPlace,
) -> tuple[float, float] | None:
    if (
        place.latitude == 0.0
        or place.longitude == 0.0
    ):
        return None
    return place.latitude, place.longitude


def _travel_date(start_date: str | None, day: int) -> date | None:
    if not start_date:
        return None
    try:
        return date.fromisoformat(start_date) + timedelta(days=day - 1)
    except ValueError:
        return None


def _record_verification_problem(
    issues: list[ValidationIssue],
    warnings: list[ValidationIssue],
    blocking: bool,
    problem: ValidationIssue,
) -> None:
    (issues if blocking else warnings).append(problem)


def _condition_support_warnings(
    conditions: TravelConditions,
) -> list[ValidationIssue]:
    warnings: list[ValidationIssue] = []
    if conditions.budget_per_person is not None:
        warnings.append(
            ValidationIssue(
                "budget_not_enforced",
                "현재 TourAPI 데이터에는 일관된 비용 정보가 없어 1인 예산을 "
                "하드 제한으로 검증하지 못했습니다.",
            )
        )
    if conditions.indoor_preference in {"indoor", "outdoor"}:
        warnings.append(
            ValidationIssue(
                "indoor_preference_not_verified",
                "실내·실외 선호는 검색 문맥에는 반영했지만 모든 후보의 "
                "구조화된 실내 여부를 검증하지 못했습니다.",
            )
        )
    return warnings


def _validate_accessibility(
    place: RetrievedPlace,
    facts: OperationalFacts | None,
    conditions: TravelConditions,
    *,
    day: int,
    slot_sequence: int,
) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
    if not conditions.mobility_constraints:
        return [], []
    requirements = _accessibility_requirements(
        conditions.mobility_constraints
    )
    if not requirements:
        return [], [
            ValidationIssue(
                "accessibility_constraint_unmapped",
                f"{place.title}에서 다음 이동 제약을 자동 판정할 수 없습니다: "
                + ", ".join(conditions.mobility_constraints),
                day,
                slot_sequence,
                place.content_id,
            )
        ]
    available = _local_accessibility(place)
    if facts is not None:
        available.update(
            {
                str(key): bool(value)
                for key, value in facts.accessibility.items()
            }
        )
    issues: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    for field_name, label in requirements.items():
        value = available.get(field_name)
        if value is False:
            issues.append(
                ValidationIssue(
                    "accessibility_requirement_failed",
                    f"{place.title}은 필수 접근성 조건({label})을 충족하지 "
                    "않는 것으로 확인됩니다.",
                    day,
                    slot_sequence,
                    place.content_id,
                )
            )
        elif value is not True:
            warnings.append(
                ValidationIssue(
                    "accessibility_unverified",
                    f"{place.title}의 접근성 조건({label})을 확인할 구조화 "
                    "정보가 없습니다.",
                    day,
                    slot_sequence,
                    place.content_id,
                )
            )
    return issues, warnings


def _accessibility_requirements(
    values: Sequence[str],
) -> dict[str, str]:
    normalized = _normalized(" ".join(values))
    result: dict[str, str] = {}
    if any(token in normalized for token in ("휠체어", "계단회피", "무장애")):
        result["wheelchairAccessibleEntrance"] = "휠체어 접근 가능한 입구"
    if "유모차" in normalized:
        result["strollerAccessible"] = "유모차 접근"
    if any(token in normalized for token in ("장애인화장실", "휠체어화장실")):
        result["wheelchairAccessibleRestroom"] = "휠체어 접근 화장실"
    if "장애인주차" in normalized:
        result["wheelchairAccessibleParking"] = "장애인 주차"
    return result


def _local_accessibility(place: RetrievedPlace) -> dict[str, bool]:
    raw = place.raw.get("type_details")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = {}
    details = raw if isinstance(raw, Mapping) else {}
    result: dict[str, bool] = {}
    baby_value = next(
        (
            value
            for key, value in details.items()
            if "chkbabycarriage" in str(key).lower()
        ),
        None,
    )
    if baby_value not in (None, ""):
        result["strollerAccessible"] = _positive_fact(str(baby_value))
    if place.parking:
        result["wheelchairAccessibleParking"] = _positive_fact(place.parking)
    return result


def _positive_fact(value: str) -> bool:
    normalized = _normalized(value)
    negative = ("불가", "없음", "안됨", "불가능", "no")
    if any(token in normalized for token in negative):
        return False
    return any(
        token in normalized
        for token in ("가능", "있음", "제공", "yes", "available")
    )


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
