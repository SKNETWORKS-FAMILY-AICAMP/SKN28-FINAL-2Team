from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import RetrievedPlace


JsonRequester = Callable[[Request, float], Mapping[str, Any]]


class OperationalFactsError(RuntimeError):
    """Raised when an external place-facts provider fails."""


@dataclass(frozen=True)
class OperationalFacts:
    source: str
    verified: bool
    business_status: str | None = None
    closed_on_date: bool | None = None
    opening_ranges: tuple[tuple[int, int], ...] = ()
    accessibility: Mapping[str, bool] = field(default_factory=dict)
    parking_options: Mapping[str, bool] = field(default_factory=dict)
    external_place_id: str | None = None


class PlaceOperationalFactsProvider(Protocol):
    def facts_for(
        self,
        place: RetrievedPlace,
        travel_date: date,
    ) -> OperationalFacts | None: ...


class HolidayCalendar(Protocol):
    def holiday_name(self, value: date) -> str | None: ...


class KoreanPublicHolidayCalendar:
    """Official fixed holidays plus optional KASI/Data.go.kr date overrides.

    Lunar and substitute holidays should be supplied through ``extra_holidays``
    or the operating-exceptions JSON. Fixed holidays are still useful for
    triggering an explicit exceptional-hours check.
    """

    FIXED = {
        (1, 1): "신정",
        (3, 1): "삼일절",
        (5, 5): "어린이날",
        (6, 6): "현충일",
        (8, 15): "광복절",
        (10, 3): "개천절",
        (10, 9): "한글날",
        (12, 25): "기독탄신일",
    }
    YEAR_SPECIFIC = {
        2026: {
            "2026-02-16": "설날 연휴",
            "2026-02-17": "설날",
            "2026-02-18": "설날 연휴",
            "2026-03-02": "3·1절 대체공휴일",
            "2026-05-24": "부처님오신날",
            "2026-05-25": "부처님오신날 대체공휴일",
            "2026-06-03": "전국동시지방선거",
            "2026-08-17": "광복절 대체공휴일",
            "2026-09-24": "추석 연휴",
            "2026-09-25": "추석",
            "2026-09-26": "추석 연휴",
            "2026-10-05": "개천절 대체공휴일",
        }
    }

    def __init__(
        self,
        extra_holidays: Mapping[str, str] | None = None,
    ) -> None:
        self._extra = dict(extra_holidays or {})

    def holiday_name(self, value: date) -> str | None:
        return (
            self._extra.get(value.isoformat())
            or self.YEAR_SPECIFIC.get(value.year, {}).get(value.isoformat())
            or self.FIXED.get((value.month, value.day))
        )


class OperationalOverrideStore:
    """Version-controlled emergency closure and exceptional-hours provider."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._payload = _read_override_file(self.path)

    @property
    def holidays(self) -> Mapping[str, str]:
        value = self._payload.get("public_holidays")
        return dict(value) if isinstance(value, Mapping) else {}

    def facts_for(
        self,
        place: RetrievedPlace,
        travel_date: date,
    ) -> OperationalFacts | None:
        closures = self._payload.get("place_exceptions")
        if not isinstance(closures, list):
            return None
        target_date = travel_date.isoformat()
        for item in closures:
            if not isinstance(item, Mapping):
                continue
            if int(item.get("content_id") or 0) != place.content_id:
                continue
            if str(item.get("date") or "") != target_date:
                continue
            closed = item.get("closed")
            ranges = _ranges_from_strings(item.get("opening_ranges"))
            return OperationalFacts(
                source="operating_exception_file",
                verified=True,
                business_status=(
                    "CLOSED_TEMPORARILY" if closed is True else "OPERATIONAL"
                ),
                closed_on_date=bool(closed),
                opening_ranges=ranges,
            )
        return None


class GooglePlacesFactsProvider:
    """Places API (New) text-search adapter for live hours and accessibility."""

    ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
    FIELD_MASK = ",".join(
        (
            "places.id",
            "places.displayName",
            "places.location",
            "places.businessStatus",
            "places.currentOpeningHours",
            "places.regularOpeningHours",
            "places.accessibilityOptions",
            "places.parkingOptions",
        )
    )

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 8.0,
        requester: JsonRequester | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Google Places API key must not be blank")
        self._api_key = api_key.strip()
        self._timeout = timeout
        self._requester = requester or _request_json

    def facts_for(
        self,
        place: RetrievedPlace,
        travel_date: date,
    ) -> OperationalFacts | None:
        body: dict[str, Any] = {
            "textQuery": " ".join(
                value for value in (place.title, place.address) if value
            ),
            "languageCode": "ko",
            "regionCode": "KR",
            "maxResultCount": 1,
        }
        if place.latitude and place.longitude:
            body["locationBias"] = {
                "circle": {
                    "center": {
                        "latitude": place.latitude,
                        "longitude": place.longitude,
                    },
                    "radius": 1000.0,
                }
            }
        request = Request(
            self.ENDPOINT,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self._api_key,
                "X-Goog-FieldMask": self.FIELD_MASK,
            },
            method="POST",
        )
        payload = self._requester(request, self._timeout)
        places = payload.get("places")
        if not isinstance(places, list) or not places:
            return None
        result = places[0]
        if not isinstance(result, Mapping):
            return None
        current = result.get("currentOpeningHours")
        regular = result.get("regularOpeningHours")
        ranges = _google_ranges_for_date(current, travel_date)
        if not ranges:
            ranges = _google_ranges_for_date(regular, travel_date)
        business_status = str(result.get("businessStatus") or "") or None
        closed_on_date: bool | None = None
        if business_status in {"CLOSED_TEMPORARILY", "CLOSED_PERMANENTLY"}:
            closed_on_date = True
        elif _hours_cover_date(current, travel_date):
            closed_on_date = not ranges
        return OperationalFacts(
            source="google_places",
            verified=True,
            business_status=business_status,
            closed_on_date=closed_on_date,
            opening_ranges=ranges,
            accessibility=_bool_mapping(result.get("accessibilityOptions")),
            parking_options=_bool_mapping(result.get("parkingOptions")),
            external_place_id=str(result.get("id") or "") or None,
        )


class CompositeOperationalFactsProvider:
    def __init__(
        self,
        providers: Sequence[PlaceOperationalFactsProvider],
    ) -> None:
        self._providers = tuple(providers)

    def facts_for(
        self,
        place: RetrievedPlace,
        travel_date: date,
    ) -> OperationalFacts | None:
        for provider in self._providers:
            try:
                facts = provider.facts_for(place, travel_date)
            except OperationalFactsError:
                continue
            if facts is not None:
                return facts
        return None


def create_operational_services_from_env(
    *,
    project_root: str | Path,
    env: Mapping[str, str] | None = None,
) -> tuple[PlaceOperationalFactsProvider | None, HolidayCalendar]:
    values = env or os.environ
    providers: list[PlaceOperationalFactsProvider] = []
    override_path = str(
        values.get("RAG_OPERATING_EXCEPTIONS_PATH") or ""
    ).strip()
    if not override_path:
        override_path = str(
            Path(project_root) / "data" / "processed" / "rag_operating_exceptions.json"
        )
    store: OperationalOverrideStore | None = None
    if Path(override_path).exists():
        store = OperationalOverrideStore(override_path)
        providers.append(store)
    google_key = str(
        values.get("GOOGLE_PLACES_API_KEY")
        or values.get("GOOGLE_MAPS_API_KEY")
        or ""
    ).strip()
    if google_key:
        providers.append(GooglePlacesFactsProvider(google_key))
    operational = (
        CompositeOperationalFactsProvider(providers) if providers else None
    )
    return operational, KoreanPublicHolidayCalendar(
        store.holidays if store is not None else None
    )


def _read_override_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OperationalFactsError(
            f"invalid operating exceptions file: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise OperationalFactsError(
            "operating exceptions root must be an object"
        )
    return payload


def _ranges_from_strings(value: Any) -> tuple[tuple[int, int], ...]:
    if not isinstance(value, list):
        return ()
    result = []
    for item in value:
        if not isinstance(item, str) or "-" not in item:
            continue
        start, end = item.split("-", 1)
        try:
            start_minutes = _hhmm(start)
            end_minutes = _hhmm(end)
        except ValueError:
            continue
        if end_minutes > start_minutes:
            result.append((start_minutes, end_minutes))
    return tuple(result)


def _google_ranges_for_date(
    value: Any,
    travel_date: date,
) -> tuple[tuple[int, int], ...]:
    if not isinstance(value, Mapping):
        return ()
    periods = value.get("periods")
    if not isinstance(periods, list):
        return ()
    result: list[tuple[int, int]] = []
    for period in periods:
        if not isinstance(period, Mapping):
            continue
        opened = period.get("open")
        closed = period.get("close")
        if not isinstance(opened, Mapping):
            continue
        if not _point_matches_date(opened, travel_date):
            continue
        start = int(opened.get("hour") or 0) * 60 + int(
            opened.get("minute") or 0
        )
        if not isinstance(closed, Mapping):
            result.append((start, 24 * 60))
            continue
        end = int(closed.get("hour") or 0) * 60 + int(
            closed.get("minute") or 0
        )
        if end == 0:
            end = 24 * 60
        if end > start:
            result.append((start, end))
    return tuple(result)


def _point_matches_date(point: Mapping[str, Any], value: date) -> bool:
    point_date = point.get("date")
    if isinstance(point_date, Mapping):
        return (
            int(point_date.get("year") or 0) == value.year
            and int(point_date.get("month") or 0) == value.month
            and int(point_date.get("day") or 0) == value.day
        )
    # Google uses Sunday=0, Python Monday=0.
    google_weekday = (value.weekday() + 1) % 7
    return int(point.get("day") or 0) == google_weekday


def _hours_cover_date(value: Any, travel_date: date) -> bool:
    if not isinstance(value, Mapping):
        return False
    special_days = value.get("specialDays")
    if isinstance(special_days, list):
        for item in special_days:
            if not isinstance(item, Mapping):
                continue
            candidate = item.get("date")
            if isinstance(candidate, Mapping) and _date_mapping_matches(
                candidate,
                travel_date,
            ):
                return True
    return bool(value.get("periods"))


def _date_mapping_matches(value: Mapping[str, Any], target: date) -> bool:
    return (
        int(value.get("year") or 0) == target.year
        and int(value.get("month") or 0) == target.month
        and int(value.get("day") or 0) == target.day
    )


def _bool_mapping(value: Any) -> dict[str, bool]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): bool(item)
        for key, item in value.items()
        if isinstance(item, bool)
    }


def _hhmm(value: str) -> int:
    hour_text, minute_text = value.strip().split(":", 1)
    hour = int(hour_text)
    minute = int(minute_text)
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("invalid HH:MM")
    return hour * 60 + minute


def _request_json(
    request: Request,
    timeout: float,
) -> Mapping[str, Any]:
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise OperationalFactsError(
            f"place facts API request failed: {exc}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise OperationalFactsError("place facts response must be an object")
    return payload
