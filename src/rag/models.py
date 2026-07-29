from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any, Mapping, Sequence


PARTY_TYPES = frozenset(
    {
        "solo",
        "non_family_two",
        "non_family_group",
        "family_two",
        "family_group",
        "with_children",
        "with_parents",
        "three_generations",
    }
)
LOCAL_TRANSPORTS = frozenset(
    {"rental_car", "own_car", "public_transit", "taxi", "mixed"}
)
VISIT_PREFERENCES = frozenset(
    {
        "nature",
        "history",
        "culture",
        "market_shopping",
        "leisure",
        "theme_park",
        "trail",
        "festival",
        "food_cafe",
        "experience",
    }
)
PACES = frozenset({"relaxed", "balanced", "packed"})


def _strings(value: Any) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, str):
        values: Sequence[Any] = (value,)
    elif isinstance(value, Sequence):
        values = value
    else:
        raise ValueError("expected a string or a list of strings")
    return tuple(
        dict.fromkeys(str(item).strip() for item in values if str(item).strip())
    )


def _optional_int(value: Any) -> int | None:
    return None if value in (None, "") else int(value)


def _optional_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _optional_time(value: Any, *, field_name: str) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", text):
        raise ValueError(f"{field_name} must use HH:MM format")
    return text


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    raise ValueError("expected a boolean or null")


@dataclass(frozen=True)
class RequiredDayItinerary:
    day: int
    place_names: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "place_names": list(self.place_names),
        }


def _required_day_itineraries(
    value: Any,
) -> tuple[RequiredDayItinerary, ...]:
    if value in (None, "", (), []):
        return ()
    raw_items: list[Mapping[str, Any]] = []
    if isinstance(value, Mapping):
        raw_items = [
            {"day": day, "place_names": places}
            for day, places in value.items()
        ]
    elif isinstance(value, Sequence) and not isinstance(value, str):
        for item in value:
            if not isinstance(item, Mapping):
                raise ValueError(
                    "required_day_itineraries items must be objects"
                )
            raw_items.append(item)
    else:
        raise ValueError(
            "required_day_itineraries must be a mapping or a list"
        )

    grouped: dict[int, list[str]] = {}
    for item in raw_items:
        day = int(item.get("day") or 0)
        if not 1 <= day <= 30:
            raise ValueError(
                "required_day_itineraries day must be between 1 and 30"
            )
        names = _strings(
            item.get("place_names")
            or item.get("places")
            or item.get("must_visit_places")
        )
        if not names:
            raise ValueError(
                "required_day_itineraries place_names must not be empty"
            )
        grouped.setdefault(day, [])
        grouped[day].extend(names)
    return tuple(
        RequiredDayItinerary(
            day=day,
            place_names=tuple(dict.fromkeys(grouped[day])),
        )
        for day in sorted(grouped)
    )


def _merge_required_day_itineraries(
    current: Any,
    incoming: Any,
) -> list[dict[str, Any]]:
    merged = _required_day_itineraries(
        [
            *(
                current
                if isinstance(current, Sequence)
                and not isinstance(current, str)
                else []
            ),
            *(
                incoming
                if isinstance(incoming, Sequence)
                and not isinstance(incoming, str)
                else []
            ),
        ]
    )
    return [item.to_dict() for item in merged]


@dataclass(frozen=True)
class TravelConditions:
    region: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    duration_days: int | None = None
    party_type: str | None = None
    local_transport: str | None = None
    preferred_visit_types: tuple[str, ...] = ()
    companion_count: int | None = None
    purpose_codes: tuple[str, ...] = ()
    pace: str | None = None
    arrival_time: str | None = None
    departure_time: str | None = None
    entry_point: str | None = None
    exit_point: str | None = None
    accommodation_address: str | None = None
    preferred_places: tuple[str, ...] = ()
    preferred_foods: tuple[str, ...] = ()
    include_breakfast: bool | None = None
    travel_styles: tuple[str, ...] = ()
    must_visit_places: tuple[str, ...] = ()
    required_day_itineraries: tuple[RequiredDayItinerary, ...] = ()
    excluded_places: tuple[str, ...] = ()
    excluded_foods: tuple[str, ...] = ()
    avoid_long_distance: bool | None = None
    opening_hours_constraints: tuple[str, ...] = ()
    parking_required: bool | None = None
    indoor_preference: str | None = None
    budget_per_person: int | None = None
    mobility_constraints: tuple[str, ...] = ()
    explicit_fields: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> TravelConditions:
        raw = value or {}
        duration = _optional_int(raw.get("duration_days"))
        if duration is not None and not 1 <= duration <= 30:
            raise ValueError("duration_days must be between 1 and 30")

        party = _optional_text(raw.get("party_type"))
        if party is not None and party not in PARTY_TYPES:
            raise ValueError(f"invalid party_type: {party}")

        transport = _optional_text(raw.get("local_transport"))
        if transport is not None and transport not in LOCAL_TRANSPORTS:
            raise ValueError(f"invalid local_transport: {transport}")

        preferences = _strings(raw.get("preferred_visit_types"))
        invalid_preferences = sorted(set(preferences) - VISIT_PREFERENCES)
        if invalid_preferences:
            raise ValueError(
                "invalid preferred_visit_types: " + ", ".join(invalid_preferences)
            )

        pace = _optional_text(raw.get("pace"))
        if pace is not None and pace not in PACES:
            raise ValueError(f"invalid pace: {pace}")

        companion_count = _optional_int(raw.get("companion_count"))
        budget = _optional_int(raw.get("budget_per_person"))
        if companion_count is not None and companion_count < 0:
            raise ValueError("companion_count must be zero or greater")
        if budget is not None and budget < 0:
            raise ValueError("budget_per_person must be zero or greater")
        indoor_preference = _optional_text(raw.get("indoor_preference"))
        if indoor_preference not in (None, "indoor", "outdoor", "either"):
            raise ValueError(
                f"invalid indoor_preference: {indoor_preference}"
            )
        required_day_itineraries = _required_day_itineraries(
            raw.get("required_day_itineraries")
            or raw.get("must_visit_by_day")
        )
        if duration is not None and any(
            item.day > duration for item in required_day_itineraries
        ):
            raise ValueError(
                "required day itinerary exceeds duration_days"
            )

        return cls(
            region=_optional_text(raw.get("region")),
            start_date=_optional_text(raw.get("start_date")),
            end_date=_optional_text(raw.get("end_date")),
            duration_days=duration,
            party_type=party,
            local_transport=transport,
            preferred_visit_types=preferences,
            companion_count=companion_count,
            purpose_codes=_strings(raw.get("purpose_codes")),
            pace=pace,
            arrival_time=_optional_time(
                raw.get("arrival_time") or raw.get("trip_start_time"),
                field_name="trip_start_time",
            ),
            departure_time=_optional_time(
                raw.get("departure_time")
                or raw.get("airport_arrival_deadline"),
                field_name="airport_arrival_deadline",
            ),
            entry_point=_optional_text(
                raw.get("entry_point") or raw.get("start_point")
            ),
            exit_point=_optional_text(
                raw.get("exit_point")
                or raw.get("end_point")
                or raw.get("departure_airport")
            ),
            accommodation_address=_optional_text(
                raw.get("accommodation_address") or raw.get("accommodation")
            ),
            preferred_places=_strings(raw.get("preferred_places")),
            preferred_foods=_strings(
                raw.get("preferred_foods")
                or raw.get("meal_menu_preferences")
            ),
            include_breakfast=_optional_bool(raw.get("include_breakfast")),
            travel_styles=_strings(raw.get("travel_styles")),
            must_visit_places=_strings(
                raw.get("must_visit_places") or raw.get("required_itinerary")
            ),
            required_day_itineraries=required_day_itineraries,
            excluded_places=_strings(raw.get("excluded_places")),
            excluded_foods=_strings(raw.get("excluded_foods")),
            avoid_long_distance=_optional_bool(raw.get("avoid_long_distance")),
            opening_hours_constraints=_strings(
                raw.get("opening_hours_constraints")
            ),
            parking_required=_optional_bool(raw.get("parking_required")),
            indoor_preference=indoor_preference,
            budget_per_person=budget,
            mobility_constraints=_strings(raw.get("mobility_constraints")),
            explicit_fields=_strings(raw.get("explicit_fields")),
        )

    def merged_with(self, newer: TravelConditions) -> TravelConditions:
        current = self.to_dict()
        incoming = newer.to_dict()
        list_fields = {
            "preferred_visit_types",
            "purpose_codes",
            "preferred_places",
            "preferred_foods",
            "travel_styles",
            "must_visit_places",
            "excluded_places",
            "excluded_foods",
            "opening_hours_constraints",
            "mobility_constraints",
            "explicit_fields",
        }
        for key, value in incoming.items():
            if key == "required_day_itineraries":
                if value:
                    current[key] = _merge_required_day_itineraries(
                        current.get(key) or [],
                        value,
                    )
            elif key in list_fields:
                if value:
                    current[key] = list(
                        dict.fromkeys([*(current.get(key) or []), *value])
                    )
            elif value is not None:
                current[key] = value
        return TravelConditions.from_mapping(current)

    def missing_required_fields(self) -> tuple[str, ...]:
        missing: list[str] = []
        if self.duration_days is None:
            missing.append("duration_days")
        if self.party_type is None:
            missing.append("party_type")
        if self.local_transport is None:
            missing.append("local_transport")
        if not self.preferred_visit_types:
            missing.append("preferred_visit_types")
        return tuple(missing)

    def missing_conditional_fields(self) -> tuple[str, ...]:
        missing: list[str] = []
        if self.departure_time is not None and self.exit_point is None:
            missing.append("departure_airport")
        return tuple(missing)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key, value in tuple(payload.items()):
            if isinstance(value, tuple):
                payload[key] = list(value)
        payload["required_day_itineraries"] = [
            item.to_dict() for item in self.required_day_itineraries
        ]
        return payload

    def to_aihub_dict(self) -> dict[str, Any]:
        missing = self.missing_required_fields()
        if missing:
            raise ValueError(
                "missing required AIHub conditions: " + ", ".join(missing)
            )
        payload = self.to_dict()
        payload.pop("explicit_fields", None)
        return payload


@dataclass(frozen=True)
class PlaceSearchFilters:
    datasets: tuple[str, ...] = ()
    target_collections: tuple[str, ...] = ()
    place_subtypes: tuple[str, ...] = ()
    recommendation_scopes: tuple[str, ...] = ("default",)
    content_type_ids: tuple[int, ...] = ()
    cities: tuple[str, ...] = ()
    districts: tuple[str, ...] = ()
    itinerary_roles: tuple[str, ...] = ()
    route_eligible: bool | None = True
    schedule_eligible: bool | None = True
    requires_verification: bool | None = False


@dataclass(frozen=True)
class RetrievedPlace:
    content_id: int
    title: str
    latitude: float
    longitude: float
    similarity_score: float
    rank: int
    dataset: str = ""
    target_collection: str = ""
    itinerary_role: str = ""
    tags: tuple[str, ...] = ()
    address: str = ""
    opening_hours: str = ""
    closed_days: str = ""
    parking: str = ""
    reservation: str = ""
    use_fee: str = ""
    rating: float | None = None
    rating_count: int | None = None
    overview: str = ""
    route_eligible: bool = True
    schedule_eligible: bool = True
    requires_verification: bool = False
    distance_km: float | None = None
    slot_score: float | None = None
    score_breakdown: Mapping[str, float] = field(default_factory=dict)
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["tags"] = list(self.tags)
        payload["score_breakdown"] = dict(self.score_breakdown)
        payload["raw"] = dict(self.raw)
        return payload


@dataclass(frozen=True)
class PlaceSearchResponse:
    query: str
    filters: PlaceSearchFilters
    total_candidates: int
    places: tuple[RetrievedPlace, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "filters": asdict(self.filters),
            "total_candidates": self.total_candidates,
            "places": [place.to_dict() for place in self.places],
        }


@dataclass(frozen=True)
class SlotRequest:
    day: int
    sequence: int
    role: str
    category: str
    target_collections: tuple[str, ...]
    itinerary_roles: tuple[str, ...]
    stay_minutes: int | None
    latitude: float | None
    longitude: float | None
    radius_km: float | None
    template_source: str = "aihub"
    route_anchor: str | None = None
    slot_kind: str = "tourism"
    meal_type: str | None = None


@dataclass(frozen=True)
class SlotCandidates:
    slot: SlotRequest
    query: str
    candidates: tuple[RetrievedPlace, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot": asdict(self.slot),
            "query": self.query,
            "candidates": [item.to_dict() for item in self.candidates],
        }


@dataclass(frozen=True)
class ItineraryChoice:
    day: int
    slot_sequence: int
    content_id: int
    stay_minutes: int
    reason: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ItineraryChoice:
        reason = str(value.get("reason") or "").strip()
        if not reason:
            raise ValueError("itinerary choice reason is blank")
        stay_minutes = int(value.get("stay_minutes") or 0)
        if not 20 <= stay_minutes <= 360:
            raise ValueError("stay_minutes must be between 20 and 360")
        return cls(
            day=int(value["day"]),
            slot_sequence=int(value["slot_sequence"]),
            content_id=int(value["content_id"]),
            stay_minutes=stay_minutes,
            reason=reason[:300],
        )


@dataclass(frozen=True)
class ItineraryDraft:
    choices: tuple[ItineraryChoice, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ItineraryDraft:
        choices = value.get("choices")
        if not isinstance(choices, list):
            raise ValueError("itinerary draft must contain a choices list")
        return cls(tuple(ItineraryChoice.from_mapping(item) for item in choices))

    def to_dict(self) -> dict[str, Any]:
        return {"choices": [asdict(choice) for choice in self.choices]}


@dataclass(frozen=True)
class ScheduledStop:
    day: int
    sequence: int
    content_id: int
    title: str
    start_time: str
    end_time: str
    stay_minutes: int
    distance_from_previous_km: float | None
    reason: str
    source: str = "TourAPI"
    slot_kind: str = "tourism"
    meal_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    day: int | None = None
    slot_sequence: int | None = None
    content_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    issues: tuple[ValidationIssue, ...]
    schedule: tuple[ScheduledStop, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "issues": [issue.to_dict() for issue in self.issues],
            "schedule": [stop.to_dict() for stop in self.schedule],
        }
