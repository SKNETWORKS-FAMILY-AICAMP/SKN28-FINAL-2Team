from __future__ import annotations

from dataclasses import dataclass, field

from ..models.travel_condition import LocalTransport, VisitPreference

VISIT_PREFERENCE_KEYWORDS: dict[VisitPreference, tuple[str, ...]] = {
    VisitPreference.NATURE: ("자연", "해변", "숲", "오름", "공원", "힐링"),
    VisitPreference.HISTORY: ("역사", "유적", "고택", "박물관"),
    VisitPreference.CULTURE: ("문화", "전시", "미술관", "박물관", "공연"),
    VisitPreference.MARKET_SHOPPING: ("시장", "쇼핑", "상점", "마켓"),
    VisitPreference.LEISURE: ("힐링", "휴식", "카페", "산책"),
    VisitPreference.THEME_PARK: ("테마파크", "놀이", "체험"),
    VisitPreference.TRAIL: ("트래킹", "등산", "올레", "둘레길", "숲길"),
    VisitPreference.FESTIVAL: ("축제", "행사"),
    VisitPreference.FOOD_CAFE: ("맛집", "음식점", "카페", "식당"),
    VisitPreference.EXPERIENCE: ("체험", "액티비티", "레저"),
}

_DEFAULT_RADIUS_KM: dict[str, float] = {
    LocalTransport.RENTAL_CAR.value: 40.0,
    LocalTransport.OWN_CAR.value: 40.0,
    LocalTransport.TAXI.value: 20.0,
    LocalTransport.PUBLIC_TRANSIT.value: 15.0,
    LocalTransport.MIXED.value: 25.0,
}

_DEFAULT_SLOT_LIMITS: dict[str, int] = {
    "visit": 3,
    "activity": 3,
    "food": 2,
    "shopping": 2,
}


@dataclass(frozen=True)
class PlannerConfig:
    similarity_weight: float = 0.5
    proximity_weight: float = 0.3
    style_weight: float = 0.2
    max_radius_km: dict[str, float] = field(
        default_factory=lambda: dict(_DEFAULT_RADIUS_KM)
    )
    default_radius_km: float = 25.0
    slot_limits: dict[str, int] = field(
        default_factory=lambda: dict(_DEFAULT_SLOT_LIMITS)
    )
    default_limit: int = 3

    def radius_for(self, local_transport: LocalTransport) -> float:
        return self.max_radius_km.get(local_transport.value, self.default_radius_km)

    def limit_for(self, role: str) -> int:
        return self.slot_limits.get(role, self.default_limit)
