from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from ..aihub.similarity import (
    LocalTransport,
    Pace,
    PartyType,
    TravelCondition,
    VisitPreference,
)

# Free-chat requests that only ask for "one more X" without naming a place
# (e.g. "카페를 하나 더 추가해줘") don't map to must_visit_places/excluded_places;
# they widen the slot search itself. These are surfaced separately so the
# planner/LLM know which itinerary slot roles to re-search.
SlotRole = str  # "visit" | "activity" | "food" | "shopping"

VALID_SLOT_ROLES: tuple[str, ...] = ("visit", "activity", "food", "shopping")


@dataclass(frozen=True)
class SlotAddRequest:
    """"~를 N개 더 추가해줘" 처럼 이름 있는 장소를 지목하지 않고 개수만
    늘려달라는 요청. ``day`` 가 ``None`` 이면 특정 일차를 지목하지 않은
    것이므로, 엔진이 기본 일차(1일차)로 처리한다.
    """

    role: SlotRole
    count: int = 1
    day: int | None = None

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "SlotAddRequest | None":
        role = str(value.get("role") or "").strip()
        if role not in VALID_SLOT_ROLES:
            return None

        count = _optional_int(value.get("count")) or 1
        count = max(1, min(count, 10))  # 방어적으로 상한을 둔다.

        day = _optional_int(value.get("day"))

        return cls(role=role, count=count, day=day)

    def to_dict(self) -> dict[str, Any]:
        return {"role": self.role, "count": self.count, "day": self.day}


@dataclass(frozen=True)
class ConditionDelta:
    """What changed, as extracted by the free-chat intent-extraction prompt.

    Only additive/subtractive changes are represented for list fields so
    that :func:`apply_delta` can update the existing ``TravelCondition``
    in place (functionally) instead of rebuilding it from scratch.
    """

    add_must_visit_places: tuple[str, ...] = ()
    remove_must_visit_places: tuple[str, ...] = ()
    add_excluded_places: tuple[str, ...] = ()
    remove_excluded_places: tuple[str, ...] = ()
    add_preferred_visit_types: tuple[VisitPreference, ...] = ()
    remove_preferred_visit_types: tuple[VisitPreference, ...] = ()
    duration_days: int | None = None
    party_type: PartyType | None = None
    local_transport: LocalTransport | None = None
    pace: Pace | None = None
    budget_per_person: int | None = None
    affected_slots: tuple[SlotRole, ...] = ()
    add_slots: tuple[SlotAddRequest, ...] = ()
    notes: str = ""

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "ConditionDelta":
        return cls(
            add_must_visit_places=_string_tuple(value.get("add_must_visit_places")),
            remove_must_visit_places=_string_tuple(value.get("remove_must_visit_places")),
            add_excluded_places=_string_tuple(value.get("add_excluded_places")),
            remove_excluded_places=_string_tuple(value.get("remove_excluded_places")),
            add_preferred_visit_types=_visit_type_tuple(
                value.get("add_preferred_visit_types")
            ),
            remove_preferred_visit_types=_visit_type_tuple(
                value.get("remove_preferred_visit_types")
            ),
            duration_days=_optional_int(value.get("duration_days")),
            party_type=PartyType(value["party_type"]) if value.get("party_type") else None,
            local_transport=(
                LocalTransport(value["local_transport"])
                if value.get("local_transport")
                else None
            ),
            pace=Pace(value["pace"]) if value.get("pace") else None,
            budget_per_person=_optional_int(value.get("budget_per_person")),
            affected_slots=_string_tuple(value.get("affected_slots")),
            add_slots=_slot_add_request_tuple(value.get("add_slots")),
            notes=str(value.get("notes") or "").strip(),
        )

    def is_empty(self) -> bool:
        return self == ConditionDelta()


def apply_delta(condition: TravelCondition, delta: ConditionDelta) -> TravelCondition:
    """Return a new ``TravelCondition`` with ``delta`` merged in.

    ``TravelCondition`` is a frozen dataclass, so "updating in place" means
    replacing only the fields the delta touches; every field the person
    hasn't mentioned again is carried over untouched.
    """

    must_visit = _apply_set_ops(
        condition.must_visit_places, delta.add_must_visit_places, delta.remove_must_visit_places
    )
    excluded = _apply_set_ops(
        condition.excluded_places, delta.add_excluded_places, delta.remove_excluded_places
    )
    # A place that becomes must-visit can no longer be excluded, and vice versa.
    must_visit = tuple(place for place in must_visit if place not in excluded)
    excluded = tuple(place for place in excluded if place not in must_visit)

    visit_types = _apply_set_ops(
        condition.preferred_visit_types,
        delta.add_preferred_visit_types,
        delta.remove_preferred_visit_types,
    )
    if not visit_types:
        visit_types = condition.preferred_visit_types

    updates: dict[str, Any] = {
        "must_visit_places": must_visit,
        "excluded_places": excluded,
        "preferred_visit_types": visit_types,
    }
    if delta.duration_days is not None:
        updates["duration_days"] = delta.duration_days
    if delta.party_type is not None:
        updates["party_type"] = delta.party_type
    if delta.local_transport is not None:
        updates["local_transport"] = delta.local_transport
    if delta.pace is not None:
        updates["pace"] = delta.pace
    if delta.budget_per_person is not None:
        updates["budget_per_person"] = delta.budget_per_person

    return replace(condition, **updates)


def infer_affected_slots(delta: ConditionDelta) -> tuple[SlotRole, ...]:
    """Fall back to guessing which itinerary slots need re-search.

    Used when the chat-update prompt didn't fill ``affected_slots`` itself.
    """

    if delta.affected_slots:
        return tuple(dict.fromkeys(delta.affected_slots))

    roles: list[SlotRole] = []
    if VisitPreference.FOOD_CAFE in delta.add_preferred_visit_types or any(
        "맛집" in place or "카페" in place or "식당" in place
        for place in (*delta.add_must_visit_places, *delta.remove_must_visit_places)
    ):
        roles.append("food")
    if any(
        preference not in (VisitPreference.FOOD_CAFE,)
        for preference in (
            *delta.add_preferred_visit_types,
            *delta.remove_preferred_visit_types,
        )
    ):
        roles.append("visit")
        roles.append("activity")
    if delta.add_must_visit_places or delta.remove_must_visit_places:
        # A named place with an unknown category could be anything; re-search
        # every itinerary-stop slot to be safe.
        roles.extend(["visit", "activity", "food", "shopping"])
    # NOTE: add_slots (이름 없이 "N개 더 추가해줘" 요청)는 여기 포함시키지 않는다.
    # 이건 기존 슬롯을 다시 검색/교체하라는 신호가 아니라 새 슬롯을 만들라는
    # 신호이므로, engine.update_itinerary_from_chat에서 별도로 처리한다.
    # 여기 포함시키면 "추가"만 요청했는데 같은 role의 기존 슬롯까지 불필요하게
    # 교체돼버린다.
    if roles:
        return tuple(dict.fromkeys(roles))
    if delta.add_slots:
        # add_slots로 이미 요청 내용을 다 파악했으니, 기존 슬롯은 하나도
        # 건드릴 필요가 없다 (아래 "전부 재검색" fallback을 타면 안 됨).
        return ()
    # 정말 아무 구조화된 신호도 없는 애매한 메시지일 때만 전부 재검색한다.
    return ("visit", "activity", "food", "shopping")


def _apply_set_ops(
    current: tuple[str, ...] | tuple[VisitPreference, ...],
    add: tuple[Any, ...],
    remove: tuple[Any, ...],
) -> tuple[Any, ...]:
    remaining = [item for item in current if item not in remove]
    for item in add:
        if item not in remaining:
            remaining.append(item)
    return tuple(remaining)


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value.strip() else ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _visit_type_tuple(value: Any) -> tuple[VisitPreference, ...]:
    if not value:
        return ()
    items: list[VisitPreference] = []
    for item in value:
        try:
            items.append(VisitPreference(item))
        except ValueError:
            continue
    return tuple(items)


def _slot_add_request_tuple(value: Any) -> tuple[SlotAddRequest, ...]:
    if not value:
        return ()
    items: list[SlotAddRequest] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        request = SlotAddRequest.from_mapping(item)
        if request is not None:
            items.append(request)
    return tuple(items)


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


__all__ = [
    "ConditionDelta",
    "LocalTransport",
    "Pace",
    "PartyType",
    "SlotAddRequest",
    "TravelCondition",
    "VisitPreference",
    "apply_delta",
    "infer_affected_slots",
]
