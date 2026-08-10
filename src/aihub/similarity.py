from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from src.models.enums import  LocalTransport, Pace, PartyType, VisitPreference
from src.models.travel_condition import TravelCondition
import hashlib
import math
from typing import Any, Callable, Iterator, Mapping, Protocol, Sequence
from src.mappings.trip_feature_mapping import AIHUB_PARTY_LABELS, VISIT_TYPE_CODES, get_visit_area_type_mapping

@dataclass(frozen=True)
class TripProfile:
    travel_id: str
    duration_days: int
    party_type: PartyType
    local_transport: LocalTransport
    companion_count: int
    age_group: str | None
    purpose_codes: frozenset[str]
    visit_type_counts: Mapping[VisitPreference, int]
    usable_visit_count: int
    average_stay_minutes: float | None
    average_satisfaction: float | None

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> TripProfile:
        visit_counts = {
            preference: int(row.get(f"{preference.value}_count") or 0)
            for preference in VisitPreference
        }
        return cls(
            travel_id=str(row["travel_id"]),
            duration_days=int(row["duration_days"]),
            party_type=AIHUB_PARTY_LABELS.get(
                str(row.get("party_label") or ""),
                PartyType.NON_FAMILY_GROUP,
            ),
            local_transport=_primary_transport(row),
            companion_count=int(row.get("companion_count") or 0),
            age_group=(
                str(row.get("age_group")).strip()
                if row.get("age_group") is not None
                else None
            ),
            purpose_codes=frozenset(
                _split_codes(
                    row.get("travel_mission_check")
                    or row.get("travel_mission")
                    or row.get("travel_purpose")
                )
            ),
            visit_type_counts=visit_counts,
            usable_visit_count=int(row.get("usable_visit_count") or 0),
            average_stay_minutes=_optional_float(
                row.get("average_stay_minutes")
            ),
            average_satisfaction=_optional_float(
                row.get("average_satisfaction")
            ),
        )

    @property
    def stops_per_day(self) -> float:
        return self.usable_visit_count / max(self.duration_days, 1)


@dataclass(frozen=True)
class TripMatch:
    profile: TripProfile
    score: float
    component_scores: Mapping[str, float]
    matched_on: tuple[str, ...]
    conflicts: tuple[str, ...]


@dataclass(frozen=True)
class AIHubPatternConfig:
    """Top-K 참고 여행 선정에 쓰는 설정.

    조건 유사도는 "어떤 여행을 참고할지"만 결정하는 최소 조건(기간/동행/교통수단)만
    사용한다. 선호 방문유형(preferred_visit_types), 페이스(pace), 목적(purpose_codes)
    등 취향 관련 정보는 유사도 계산에서 제외하고, 대신 Top-K 여행의 실제 방문 기록에서
    role별 대표 키워드를 뽑아 RAG 검색 쿼리를 보강하는 데 사용한다
    (``aggregate_role_keywords`` 참고).
    """

    top_k: int = 10
    reference_keyword_top_k: int = 10
    min_usable_visits: int = 5

    def __post_init__(self) -> None:
        if self.top_k <= 0:
            raise ValueError("top_k must be greater than zero")

        if self.reference_keyword_top_k <= 0:
            raise ValueError(
                "reference_keyword_top_k must be greater than zero"
            )

        if self.reference_keyword_top_k < self.top_k:
            raise ValueError(
                "reference_keyword_top_k must be greater than or equal to top_k"
            )

        if self.min_usable_visits <= 0:
            raise ValueError("min_usable_visits must be greater than zero")


class AIHubPatternRepository(Protocol):
    def fetch_trip_profiles(
        self,
        *,
        age_groups: Sequence[str],
        duration_days: int,
        companion_rel_codes: Sequence[str],
        min_usable_visits: int,
        limit: int,
    ) -> list[TripProfile]:
        ...

    def fetch_trip_routes(
        self,
        travel_ids: Sequence[str],
    ) -> list[dict[str, Any]]:
        ...


class AIHubSimilarityRepository:
    """Read AIHub schedule patterns without using AIHub-to-TourAPI mappings."""

    def __init__(
        self,
        config: Any | None = None,
        *,
        connection_factory: Callable[[], Any] | None = None,
    ) -> None:
        if config is None and connection_factory is None:
            raise ValueError("config or connection_factory is required")

        self._config = config
        self._connection_factory = connection_factory

    def fetch_trip_profiles(
        self,
        *,
        age_groups: Sequence[str],
        duration_days: int,
        companion_rel_codes: Sequence[str],
        min_usable_visits: int,
        limit: int,
    ) -> list[TripProfile]:

        if duration_days <= 0:
            raise ValueError(
                "duration_days must be greater than zero"
            )

        if min_usable_visits <= 0:
            raise ValueError(
                "min_usable_visits must be greater than zero"
            )

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero"
            )

        normalized_age_groups = tuple(
            dict.fromkeys(
                str(age).strip()
                for age in age_groups
                if str(age).strip()
            )
        )

        if not normalized_age_groups:
            return []

        age_placeholders = ", ".join(
            ["%s"] * len(normalized_age_groups)
        )

        normalized_rel_codes = tuple(
            dict.fromkeys(
                str(code).strip()
                for code in companion_rel_codes
                if str(code).strip()
            )
        )

        # 혼자 여행
        if not normalized_rel_codes:
            companion_condition = """
                NOT EXISTS (
                    SELECT 1
                    FROM aihub_companion AS c
                    WHERE c.travel_id = t.travel_id
                )
            """

            companion_params = []

        # 친구 / 가족
        else:
            companion_placeholders = ", ".join(
                ["%s"] * len(normalized_rel_codes)
            )

            companion_condition = f"""
                EXISTS (
                    SELECT 1
                    FROM aihub_companion AS c
                    WHERE c.travel_id = t.travel_id
                    AND c.rel_cd IN ({companion_placeholders})
                )
            """

            companion_params = list(normalized_rel_codes)

        sql = _TRIP_PROFILE_SQL.format(
            age_placeholders=age_placeholders,
            companion_condition=companion_condition,
        )

        params = [
            *normalized_age_groups,
            duration_days,
            min_usable_visits,
            *companion_params,
            limit,
        ]

        with self._connect() as connection:
            cursor = connection.cursor(dictionary=True)

            try:
                cursor.execute(sql, params)

                return [
                    TripProfile.from_row(row)
                    for row in cursor.fetchall()
                ]

            finally:
                cursor.close()

    def fetch_trip_routes(
        self,
        travel_ids: Sequence[str],
    ) -> list[dict[str, Any]]:
        normalized_ids = tuple(
            dict.fromkeys(
                str(item)
                for item in travel_ids
                if item
            )
        )

        if not normalized_ids:
            return []

        placeholders = ", ".join(
            ["%s"] * len(normalized_ids)
        )

        sql = _TRIP_ROUTE_SQL.format(
            placeholders=placeholders
        )

        with self._connect() as connection:
            cursor = connection.cursor(dictionary=True)

            try:
                cursor.execute(sql, normalized_ids)
                return list(cursor.fetchall())

            finally:
                cursor.close()

    @contextmanager
    def _connect(self) -> Iterator[Any]:
        if self._connection_factory is not None:
            connection = self._connection_factory()

        else:
            try:
                import mysql.connector
            except ImportError as exc:
                raise RuntimeError(
                    "mysql-connector-python is not installed"
                ) from exc

            if isinstance(self._config, Mapping):
                kwargs = dict(self._config)
            else:
                kwargs = self._config.connection_kwargs()

            connection = mysql.connector.connect(**kwargs)

        try:
            yield connection

        finally:
            connection.close()

class AIHubPatternService:
    def __init__(
        self,
        repository: AIHubPatternRepository,
        config: AIHubPatternConfig | None = None,
    ) -> None:
        self.repository = repository
        self.config = config or AIHubPatternConfig()

    def find_reference_trips(
        self,
        condition: TravelCondition | Mapping[str, Any],
    ) -> list[TripMatch]:
        normalized = _normalize_condition(condition)

        companion_rel_codes = _companion_relation_codes(
            normalized.party_type
        )

        age_groups = _fallback_age_groups(
            normalized.age_group
        )

        print("\n========== AIHub FILTER ==========")
        print("age_group:", normalized.age_group)
        print("age_groups:", age_groups)
        print("duration_days:", normalized.duration_days)
        print("party_type:", normalized.party_type)
        print("companion_rel_codes:", companion_rel_codes)
        print("min_visits:", self.config.min_usable_visits)
        print("==================================")

        profiles = self.repository.fetch_trip_profiles(
            age_groups=age_groups,
            duration_days=normalized.duration_days,
            companion_rel_codes=companion_rel_codes,
            min_usable_visits=self.config.min_usable_visits,
            limit=self.config.top_k,
        )
        print(f"[AIHub FILTER RESULT] {len(profiles)}개")
        for profile in profiles:
            print(
                f"travel_id={profile.travel_id}, "
                f"duration={profile.duration_days}, "
                f"age_group={profile.age_group}, "
                f"party={profile.party_type}, "
                f"visits={profile.usable_visit_count}"
            )

        return [
            TripMatch(
                profile=profile,
                score=100.0,
                component_scores={
                    "age_group": 100.0,
                    "duration": 100.0,
                    "party": 100.0,
                    "visit_count": 100.0,
                },
                matched_on=(
                    "age_group",
                    "duration",
                    "party",
                    "visit_count",
                ),
                conflicts=(),
            )
            for profile in profiles
        ]
    def find_reference_keyword_trips(
        self,
        condition: TravelCondition | Mapping[str, Any],
    ) -> list[TripMatch]:
        normalized = _normalize_condition(condition)

        companion_rel_codes = _companion_relation_codes(
            normalized.party_type
        )

        age_groups = _fallback_age_groups(
            normalized.age_group
        )

        profiles = self.repository.fetch_trip_profiles(
            age_groups=age_groups,
            duration_days=normalized.duration_days,
            companion_rel_codes=companion_rel_codes,
            min_usable_visits=self.config.min_usable_visits,
            limit=self.config.reference_keyword_top_k,
        )

        return [
            TripMatch(
                profile=profile,
                score=100.0,
                component_scores={
                    "age_group": 100.0,
                    "duration": 100.0,
                    "party": 100.0,
                    "visit_count": 100.0,
                },
                matched_on=(
                    "age_group",
                    "duration",
                    "party",
                    "visit_count",
                ),
                conflicts=(),
            )
            for profile in profiles
        ]

    def build_llm_context(
        self,
        condition: TravelCondition | Mapping[str, Any],
    ) -> dict[str, Any]:
        normalized = _normalize_condition(condition)
        matches = self.find_reference_trips(normalized)
        routes = self.repository.fetch_trip_routes(
            [match.profile.travel_id for match in matches]
        )
        routes_by_trip: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for route in routes:
            routes_by_trip[str(route["travel_id"])].append(route)

        return {
            "user_constraints": normalized.to_llm_dict(),
            "reference_trip_patterns": [
                self._reference_trip_payload(
                    match,
                    routes_by_trip.get(match.profile.travel_id, []),
                )
                for match in matches
            ],
            "context_policy": {
                "priority": [
                    "user_constraints",
                    "current_verified_place_data",
                    "travel_time",
                    "reference_trip_patterns",
                ],
                "reference_usage": (
                    "Use historical patterns only for route order, regional "
                    "grouping, stops per day, and stay duration. Fill every "
                    "schedule slot with a verified TourAPI vector candidate."
                ),
                "place_source": "tourapi_vector_candidates_only",
                "aihub_tourapi_mapping": "ignored",
            },
        }

    def _score_trip(
        self,
        condition: TravelCondition,
        profile: TripProfile,
    ) -> TripMatch:
        scores: dict[str, float] = {
            "duration": _duration_similarity(
                condition.duration_days,
                profile.duration_days,
            ),
            "party": _party_compatibility(
                condition.party_type,
                profile.party_type,
            ),
            "transport": _transport_compatibility(
                condition.local_transport,
                profile.local_transport,
            ),
            "interest": _interest_similarity(condition, profile),
        }
        weights: dict[str, float] = {
            "duration": self.config.duration_weight,
            "party": self.config.party_weight,
            "transport": self.config.transport_weight,
            "interest": self.config.interest_weight,
        }
        if condition.purpose_codes:
            scores["purpose"] = _set_overlap(
                frozenset(condition.purpose_codes),
                profile.purpose_codes,
            )
            weights["purpose"] = self.config.purpose_weight
        if condition.pace is not None:
            scores["pace"] = _pace_similarity(condition.pace, profile)
            weights["pace"] = self.config.pace_weight

        weight_total = sum(weights.values())
        score = sum(scores[key] * weights[key] for key in weights) / weight_total
        matched_on = tuple(key for key, value in scores.items() if value >= 0.75)
        conflicts = tuple(key for key, value in scores.items() if value <= 0.30)
        return TripMatch(
            profile=profile,
            score=round(score * 100, 2),
            component_scores={
                key: round(value * 100, 2) for key, value in scores.items()
            },
            matched_on=matched_on,
            conflicts=conflicts,
        )

    @staticmethod
    def _reference_trip_payload(
        match: TripMatch,
        route_rows: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        rows_by_day: defaultdict[int, list[Mapping[str, Any]]] = defaultdict(list)
        for row in route_rows:
            day_no = max(int(row.get("day_no") or 1), 1)
            rows_by_day[day_no].append(row)

        days: list[dict[str, Any]] = []
        for day_no, day_rows in sorted(rows_by_day.items()):
            slots: list[dict[str, Any]] = []
            ignored_role_counts: defaultdict[str, int] = defaultdict(int)
            satisfaction_values: list[float] = []
            for row in sorted(
                day_rows,
                key=lambda item: (
                    int(item.get("visit_order") or 0),
                    str(item.get("visit_area_id") or ""),
                ),
            ):
                visit_type_code = str(row.get("visit_area_type_cd") or "")

                mapping = get_visit_area_type_mapping(visit_type_code)
                if mapping is None:
                    ignored_role_counts["unknown"] += 1
                    continue

                if not mapping.include_in_rag or mapping.slot_role is None:
                    ignored_role_counts[mapping.normalized_type] += 1
                    continue

                category = mapping.normalized_type
                role = mapping.slot_role
                longitude, latitude, coordinate_status = _clean_jeju_coordinate(
                    row.get("longitude"),
                    row.get("latitude"),
                )
                satisfaction = _optional_float(row.get("satisfaction"))
                if satisfaction is not None:
                    satisfaction_values.append(satisfaction)
                slots.append(
                    {
                        "sequence": len(slots) + 1,
                        "role": role,
                        "category": category,
                        "target_collections": list(mapping.target_collections),
                        "itinerary_roles": list(mapping.itinerary_roles),
                        "stay_minutes": _optional_int(
                            row.get("stay_minutes")
                        ),
                        "location_hint": (
                            {
                                "longitude": round(longitude, 4),
                                "latitude": round(latitude, 4),
                            }
                            if coordinate_status == "valid"
                            and longitude is not None
                            and latitude is not None
                            else None
                        ),
                    }
                )
            days.append(
                {
                    "day": day_no,
                    "region": _day_region(slots),
                    "slot_count": len(slots),
                    "slots": slots,
                    "historical_average_satisfaction": (
                        round(
                            sum(satisfaction_values)
                            / len(satisfaction_values),
                            2,
                        )
                        if satisfaction_values
                        else None
                    ),
                    "ignored_historical_anchors": dict(
                        sorted(ignored_role_counts.items())
                    ),
                }
            )

        return {
            "reference_trip_id": _reference_trip_key(match.profile.travel_id),
            "match_score": match.score,
            "match_confidence": _match_confidence(match),
            "component_scores": dict(match.component_scores),
            "matched_on": list(match.matched_on),
            "conflicts": list(match.conflicts),
            "profile": {
                "duration_days": match.profile.duration_days,
                "party_type": match.profile.party_type.value,
                "local_transport": match.profile.local_transport.value,
                "stops_per_day": round(match.profile.stops_per_day, 2),
                "average_stay_minutes": match.profile.average_stay_minutes,
                "average_satisfaction": match.profile.average_satisfaction,
            },
            "days": days,
        }


def _normalize_condition(
    condition: TravelCondition | Mapping[str, Any],
) -> TravelCondition:
    if isinstance(condition, TravelCondition):
        return condition
    return TravelCondition.from_mapping(condition)

def _companion_relation_codes(
    party_type: PartyType,
) -> tuple[str, ...]:
    if party_type == PartyType.SOLO:
        return ()

    # 친구: 형제/자매 + 친구
    if party_type in {
        PartyType.NON_FAMILY_TWO,
        PartyType.NON_FAMILY_GROUP,
    }:
        return ("5", "7")

    # 가족: 자녀 + 부모 + 조부모
    if party_type in {
        PartyType.FAMILY_TWO,
        PartyType.FAMILY_GROUP,
        PartyType.WITH_CHILDREN,
        PartyType.WITH_PARENTS,
        PartyType.THREE_GENERATIONS,
    }:
        return ("2", "3", "4")

    return ()

def _fallback_age_groups(
    age_group: str | None,
) -> tuple[str, ...]:
    """
    요청 나이대를 기준으로 ±1단계의 AIHub age_grp 코드를 반환한다.

    AIHub DB:
        20 = 20대
        30 = 30대
        40 = 40대
        50 = 50대
        60 = 60대
    """
    if not age_group:
        return ()
    
    normalized = str(age_group).strip().lower()

    if normalized.endswith("s"):
        normalized = normalized[:-1]

    try:
        age = int(normalized)
    except ValueError:
        return ()

    available_age_groups = {
        20: "20",
        30: "30",
        40: "40",
        50: "50",
        60: "60",
    }

    fallback = []

    for candidate_age in (age - 10, age, age + 10):
        if candidate_age in available_age_groups:
            fallback.append(available_age_groups[candidate_age])

    return tuple(fallback)


def _duration_similarity(requested: int, historical: int) -> float:
    difference = abs(requested - historical)
    return max(0.0, 1.0 - difference / max(requested, 2))

def _party_compatibility(requested: PartyType, historical: PartyType ) -> float:
    if requested == historical:
        return 1.0
    non_family = {
        PartyType.NON_FAMILY_TWO,
        PartyType.NON_FAMILY_GROUP,
    }
    family = {
        PartyType.FAMILY_TWO,
        PartyType.FAMILY_GROUP,
        PartyType.WITH_CHILDREN,
        PartyType.WITH_PARENTS,
        PartyType.THREE_GENERATIONS,
    }
    if requested in non_family and historical in non_family:
        return 0.75
    if requested in family and historical in family:
        return 0.65
    return 0.0


def _transport_compatibility(
    requested: LocalTransport,
    historical: LocalTransport,
) -> float:
    if requested == historical:
        return 1.0
    if LocalTransport.MIXED in {requested, historical}:
        return 0.60
    if {
        requested,
        historical,
    } == {LocalTransport.RENTAL_CAR, LocalTransport.OWN_CAR}:
        return 0.85
    if {
        requested,
        historical,
    } == {LocalTransport.PUBLIC_TRANSIT, LocalTransport.TAXI}:
        return 0.65
    if requested in {LocalTransport.RENTAL_CAR, LocalTransport.OWN_CAR}:
        return 0.35
    return 0.15


def _interest_similarity(
    condition: TravelCondition,
    profile: TripProfile,
) -> float:
    target_per_type = max(profile.duration_days * 0.5, 1.0)
    coverage = [
        min(
            int(profile.visit_type_counts.get(preference, 0))
            / target_per_type,
            1.0,
        )
        for preference in condition.preferred_visit_types
    ]
    return sum(coverage) / len(coverage)


def _set_overlap(requested: frozenset[str], historical: frozenset[str]) -> float:
    if not requested:
        return 1.0
    return len(requested & historical) / len(requested)


def _pace_similarity(pace: Pace, profile: TripProfile) -> float:
    stops_per_day = profile.stops_per_day
    average_stay = profile.average_stay_minutes or 0
    if pace == Pace.RELAXED:
        return 1.0 if stops_per_day <= 4.5 or average_stay >= 75 else 0.25
    if pace == Pace.PACKED:
        return 1.0 if stops_per_day >= 6 else 0.25
    return 1.0 if 4 <= stops_per_day <= 6 else 0.60


def _primary_transport(row: Mapping[str, Any]) -> LocalTransport:
    counts = {
        LocalTransport.RENTAL_CAR: int(row.get("rental_car_count") or 0),
        LocalTransport.OWN_CAR: int(row.get("own_car_count") or 0),
        LocalTransport.PUBLIC_TRANSIT: int(
            row.get("public_transit_count") or 0
        ),
        LocalTransport.TAXI: int(row.get("taxi_count") or 0),
    }
    winner, count = max(counts.items(), key=lambda item: item[1])
    if count > 0:
        return winner
    movement_name = str(row.get("movement_name") or "")
    if movement_name == "자가용":
        return LocalTransport.OWN_CAR
    if movement_name == "대중교통 등":
        return LocalTransport.PUBLIC_TRANSIT
    return LocalTransport.MIXED


def _day_region(slots: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    points = [
        (
            float(slot["location_hint"]["latitude"]),
            float(slot["location_hint"]["longitude"]),
        )
        for slot in slots
        if slot.get("location_hint")
    ]
    if not points:
        return None
    center_latitude = sum(point[0] for point in points) / len(points)
    center_longitude = sum(point[1] for point in points) / len(points)
    distances = sorted(
        _haversine_km(
            center_latitude,
            center_longitude,
            latitude,
            longitude,
        )
        for latitude, longitude in points
    )
    percentile_index = max(math.ceil(len(distances) * 0.8) - 1, 0)
    historical_radius = distances[percentile_index]
    return {
        "center": {
            "longitude": round(center_longitude, 4),
            "latitude": round(center_latitude, 4),
        },
        "historical_radius_km": round(historical_radius, 1),
        "vector_search_radius_km": round(
            min(max(historical_radius + 5, 5), 40),
            1,
        ),
        "coordinate_coverage": round(len(points) / len(slots), 2),
    }


def _haversine_km(
    latitude1: float,
    longitude1: float,
    latitude2: float,
    longitude2: float,
) -> float:
    earth_radius_km = 6371.0088
    latitude_delta = math.radians(latitude2 - latitude1)
    longitude_delta = math.radians(longitude2 - longitude1)
    first_latitude = math.radians(latitude1)
    second_latitude = math.radians(latitude2)
    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(first_latitude)
        * math.cos(second_latitude)
        * math.sin(longitude_delta / 2) ** 2
    )
    return earth_radius_km * 2 * math.asin(math.sqrt(haversine))


def _reference_trip_key(travel_id: str) -> str:
    digest = hashlib.sha256(travel_id.encode("utf-8")).hexdigest()[:16]
    return f"aihub-trip:{digest}"


def _match_confidence(match: TripMatch) -> str:
    if match.score >= 80 and not match.conflicts:
        return "high"
    if match.score >= 60:
        return "medium"
    return "low"


def _split_codes(value: Any) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    return tuple(
        item.strip()
        for item in str(value).replace(",", ";").split(";")
        if item.strip()
    )


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _optional_string(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _clean_jeju_coordinate(
    longitude: Any,
    latitude: Any,
) -> tuple[float | None, float | None, str]:
    if longitude in (None, "") or latitude in (None, ""):
        return None, None, "missing"
    try:
        normalized_longitude = float(longitude)
        normalized_latitude = float(latitude)
    except (TypeError, ValueError):
        return None, None, "invalid"
    if not (
        126.0 <= normalized_longitude <= 127.0
        and 33.0 <= normalized_latitude <= 34.0
    ):
        return None, None, "out_of_bounds"
    return (
        round(normalized_longitude, 7),
        round(normalized_latitude, 7),
        "valid",
    )


_VISIT_COUNT_SQL = ",\n".join(
    (
        "            SUM(CASE WHEN v.visit_area_type_cd IN "
        f"({', '.join(repr(code) for code in codes)}) THEN 1 ELSE 0 END) "
        f"AS {preference.value}_count"
    )
    for preference, codes in VISIT_TYPE_CODES.items()
)

_TRIP_PROFILE_SQL = f"""
    WITH visit_profile AS (
        SELECT
            v.travel_id,

            COUNT(
                DISTINCT CASE
                    WHEN v.visit_area_type_cd NOT IN ('9', '12', '24')
                    THEN v.visit_area_id
                END
            ) AS usable_visit_count,

            AVG(
                CASE
                    WHEN v.visit_area_type_cd NOT IN ('9', '12', '24')
                    THEN v.residence_time_min
                END
            ) AS average_stay_minutes,

            AVG(
                CASE
                    WHEN v.visit_area_type_cd NOT IN ('9', '12', '24')
                    THEN v.dgstfn
                END
            ) AS average_satisfaction,

{_VISIT_COUNT_SQL}

        FROM aihub_visit AS v

        WHERE v.visit_area_type_cd NOT IN ('21', '22', '23')

        GROUP BY v.travel_id
    ),

    movement_profile AS (
        SELECT
            m.travel_id,

            SUM(
                COALESCE(m.mvmn_cd_1 = '2', 0)
                + COALESCE(m.mvmn_cd_2 = '2', 0)
            ) AS rental_car_count,

            SUM(
                COALESCE(m.mvmn_cd_1 = '1', 0)
                + COALESCE(m.mvmn_cd_2 = '1', 0)
            ) AS own_car_count,

            SUM(
                COALESCE(m.mvmn_cd_1 = '4', 0)
                + COALESCE(m.mvmn_cd_2 = '4', 0)
            ) AS taxi_count,

            SUM(
                COALESCE(
                    m.mvmn_cd_1 IN (
                        '5', '6', '7', '8',
                        '11', '12', '13', '50'
                    ),
                    0
                )
                +
                COALESCE(
                    m.mvmn_cd_2 IN (
                        '5', '6', '7', '8',
                        '11', '12', '13', '50'
                    ),
                    0
                )
            ) AS public_transit_count

        FROM aihub_move AS m

        GROUP BY m.travel_id
    )

    SELECT
        t.travel_id,

        DATEDIFF(
            t.travel_end_ymd,
            t.travel_start_ymd
        ) + 1 AS duration_days,

        r.age_grp AS age_group,

        r.travel_status_accompany AS party_label,

        r.travel_companions_num AS companion_count,

        t.mvmn_nm AS movement_name,

        t.travel_purpose,
        t.travel_mission,
        t.travel_mission_check,

        vp.usable_visit_count,
        vp.average_stay_minutes,
        vp.average_satisfaction,

        vp.nature_count,
        vp.history_count,
        vp.culture_count,
        vp.market_shopping_count,
        vp.leisure_count,
        vp.theme_park_count,
        vp.trail_count,
        vp.festival_count,
        vp.food_cafe_count,
        vp.experience_count,

        COALESCE(mp.rental_car_count, 0) AS rental_car_count,
        COALESCE(mp.own_car_count, 0) AS own_car_count,
        COALESCE(mp.taxi_count, 0) AS taxi_count,
        COALESCE(mp.public_transit_count, 0) AS public_transit_count

    FROM aihub_travel AS t

    JOIN aihub_traveller AS r
      ON r.traveler_id = t.traveler_id

    JOIN visit_profile AS vp
      ON vp.travel_id = t.travel_id

    LEFT JOIN movement_profile AS mp
      ON mp.travel_id = t.travel_id

    WHERE
        r.age_grp IN ({{age_placeholders}})

        AND DATEDIFF(
            t.travel_end_ymd,
            t.travel_start_ymd
        ) + 1 = %s

        AND vp.usable_visit_count >= %s

        AND {{companion_condition}}

    ORDER BY
        vp.usable_visit_count DESC,
        t.travel_id

    LIMIT %s
"""


_TRIP_ROUTE_SQL = """
    SELECT
        t.travel_id,
        DATEDIFF(
            v.visit_start_ymd,
            t.travel_start_ymd
        ) + 1 AS day_no,
        v.visit_area_id,
        v.visit_order,
        v.visit_area_nm AS place_name,
        v.road_nm_addr AS road_address,
        v.lotno_addr AS lot_address,
        v.x_coord AS longitude,
        v.y_coord AS latitude,
        v.visit_area_type_cd,
        v.residence_time_min AS stay_minutes,
        v.dgstfn AS satisfaction

    FROM aihub_travel AS t

    JOIN aihub_visit AS v
      ON v.travel_id = t.travel_id

    WHERE t.travel_id IN ({placeholders})
      AND v.visit_area_type_cd NOT IN ('21', '22', '23')

    ORDER BY
        t.travel_id,
        day_no,
        v.visit_order,
        v.visit_area_id
"""