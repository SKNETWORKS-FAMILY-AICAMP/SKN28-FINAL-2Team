from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from ..models.enums import LocalTransport, Pace, PartyType, VisitPreference

SlotRole = str  # "visit" | "activity" | "food" | "shopping"

VALID_SLOT_ROLES: tuple[str, ...] = (
    "visit",
    "activity",
    "food",
    "shopping",
)


@dataclass(frozen=True)
class TravelCondition:
    duration_days: int
    party_type: PartyType
    local_transport: LocalTransport
    preferred_visit_types: tuple[VisitPreference, ...]
    companion_count: int
    region: str | None = None
    age_group: str | None = None

    purpose_codes: tuple[str, ...] = ()
    pace: Pace | None = None
    arrival_time: str | None = None
    departure_time: str | None = None
    entry_point: str | None = None
    accommodation_address: str | None = None
    must_visit_places: tuple[str, ...] = ()
    excluded_places: tuple[str, ...] = ()
    mobility_constraints: tuple[str, ...] = ()
    

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "TravelCondition":
        return cls(
            duration_days=_optional_int(value.get("duration_days")) or 1,
            party_type=PartyType(value["party_type"]),
            local_transport=LocalTransport(value["local_transport"]),
            preferred_visit_types=_visit_type_tuple(value.get("preferred_visit_types")),
            companion_count=_optional_int(value.get("companion_count")) or 0,
            region=str(value.get("region") or "").strip() or None,
            age_group=str(value.get("age_group") or "").strip() or None,
            purpose_codes=_string_tuple(value.get("purpose_codes")),
            pace=Pace(value["pace"]) if value.get("pace") else None,
            arrival_time=value.get("arrival_time"),
            departure_time=value.get("departure_time"),
            entry_point=value.get("entry_point"),
            accommodation_address=value.get("accommodation_address"),
            must_visit_places=_string_tuple(value.get("must_visit_places")),
            excluded_places=_string_tuple(value.get("excluded_places")),
            mobility_constraints=_string_tuple(value.get("mobility_constraints")
            ),
        )

    def to_llm_dict(self) -> dict[str, Any]:
        return {
            "duration_days": self.duration_days,
            "party_type": self.party_type.value,
            "local_transport": self.local_transport.value,
            "preferred_visit_types": [
                preference.value
                for preference in self.preferred_visit_types
            ],
            "region": self.region,
            "companion_count": self.companion_count,
            "purpose_codes": list(self.purpose_codes),
            "pace": self.pace.value if self.pace else None,
            "arrival_time": self.arrival_time,
            "departure_time": self.departure_time,
            "entry_point": self.entry_point,
            "accommodation_address": self.accommodation_address,
            "must_visit_places": list(self.must_visit_places),
            "excluded_places": list(self.excluded_places),
            "mobility_constraints": list(self.mobility_constraints),
        }

@dataclass(frozen=True)
class SlotAddRequest:
    role: SlotRole
    count: int = 1
    day: int | None = None

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "SlotAddRequest | None":
        role = str(value.get("role") or "").strip()
        if role not in VALID_SLOT_ROLES:
            return None

        count = _optional_int(value.get("count")) or 1
        count = max(1, min(count, 10))

        day = _optional_int(value.get("day"))

        return cls(role=role, count=count, day=day)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "count": self.count,
            "day": self.day,
        }



@dataclass(frozen=True)
class ConditionDelta:
    add_must_visit_places: tuple[str, ...] = ()
    remove_must_visit_places: tuple[str, ...] = ()
    add_excluded_places: tuple[str, ...] = ()
    remove_excluded_places: tuple[str, ...] = ()
    add_preferred_visit_types: tuple[VisitPreference, ...] = ()
    remove_preferred_visit_types: tuple[VisitPreference, ...] = ()
    duration_days: int | None = None
    region: str | None = None
    party_type: PartyType | None = None
    local_transport: LocalTransport | None = None
    pace: Pace | None = None
    affected_slots: tuple[SlotRole, ...] = ()
    add_slots: tuple[SlotAddRequest, ...] = ()
    notes: str = ""
    # "edit"      -> 사용자가 실제로 일정을 바꿔달라고 요청함 (기존 동작)
    # "recommend" -> 사용자가 단순히 후보를 보고 싶어함 (일정에는 반영하지 않고
    #                채팅창에만 후보를 보여준다)
    mode: str = "edit"
    # 사용자가 "1일차", "둘째 날"처럼 특정 일차를 명시했을 때만 채워지는 값.
    # 특정 일차를 언급하지 않았다면 None이며, 이 경우 영향 범위를 day로
    # 좁히지 않는다.
    target_day: int | None = None
    # "A 다음에 B 추가해줘" / "A 앞에 B 추가해줘"처럼 위치 기준이 되는
    # 기존 일정 속 장소명. 둘 다 비어 있으면 위치를 지정하지 않은
    # 것이므로 기존 방식(해당 day 맨 뒤)으로 추가한다.
    insert_after: str | None = None
    insert_before: str | None = None
    # "아침/점심/오후/저녁"처럼 시간대로 위치를 지정했을 때만 채워지는 값.
    # insert_after/insert_before가 있으면 그쪽이 우선한다.
    time_period: str | None = None

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "ConditionDelta":
        mode = str(value.get("mode") or "edit").strip().lower()
        if mode not in ("edit", "recommend"):
            mode = "edit"

        time_period = str(value.get("time_period") or "").strip().lower() or None
        if time_period not in (None, "morning", "lunch", "afternoon", "evening"):
            time_period = None

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
            region=str(value.get("region") or "").strip() or None,
            party_type=PartyType(value["party_type"])
            if value.get("party_type")
            else None,
            local_transport=LocalTransport(value["local_transport"])
            if value.get("local_transport")
            else None,
            pace=Pace(value["pace"]) if value.get("pace") else None,
            affected_slots=_string_tuple(value.get("affected_slots")),
            add_slots=_slot_add_request_tuple(value.get("add_slots")),
            notes=str(value.get("notes") or "").strip(),
            mode=mode,
            target_day=_optional_int(value.get("target_day")),
            insert_after=(str(value.get("insert_after") or "").strip() or None),
            insert_before=(str(value.get("insert_before") or "").strip() or None),
            time_period=time_period,
        )

    def is_empty(self) -> bool:
        if self.mode == "recommend":
            # recommend 모드는 조건을 바꾸는 것이 아니라 후보만 보여주는
            # 요청이므로, 다른 필드가 모두 비어 있어도 "아무 것도 안 해도
            # 되는 메시지"로 취급하면 안 된다.
            return False
        return replace(self, notes="", mode="edit", target_day=None) == ConditionDelta()

def apply_delta(condition: TravelCondition, delta: ConditionDelta) -> TravelCondition:

    must_visit = _apply_set_ops(
        condition.must_visit_places, delta.add_must_visit_places, delta.remove_must_visit_places
    )
    excluded = _apply_set_ops(
        condition.excluded_places, delta.add_excluded_places, delta.remove_excluded_places
    )
    
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
    if delta.region is not None:
        updates["region"] = delta.region
    if delta.party_type is not None:
        updates["party_type"] = delta.party_type
    if delta.local_transport is not None:
        updates["local_transport"] = delta.local_transport
    if delta.pace is not None:
        updates["pace"] = delta.pace

    return replace(condition, **updates)


def infer_affected_slots(delta: ConditionDelta) -> tuple[SlotRole, ...]:

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
