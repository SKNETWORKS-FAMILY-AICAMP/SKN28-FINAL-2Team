from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ItineraryStop:
    day: int
    sequence: int
    content_id: int
    title: str = ""
    longitude: float | None = None
    latitude: float | None = None


@dataclass(frozen=True)
class NormalizedItinerary:
    duration_days: int
    conditions: dict[str, Any]
    tourism_stops: tuple[ItineraryStop, ...]


@dataclass(frozen=True)
class PackageItem:
    day: int | None
    sequence: int | None
    item_type: str
    content_id: int
    title: str = ""
    stay_minutes: int | None = None
    longitude: float | None = None
    latitude: float | None = None


@dataclass(frozen=True)
class PackageCandidate:
    package_id: str
    title: str
    summary: str
    region: str
    duration_days: int
    estimated_price: int
    match_profile: dict[str, Any]
    items: tuple[PackageItem, ...]

    @property
    def tourism_items(self) -> tuple[PackageItem, ...]:
        return tuple(item for item in self.items if item.item_type == "tourism")


@dataclass(frozen=True)
class ScoreBreakdown:
    exact_overlap: float
    route_fit: float
    profile_fit: float
    nearby_fit: float
    total: float


@dataclass(frozen=True)
class ScoredPackage:
    package: PackageCandidate
    score: ScoreBreakdown
    exact_match_count: int
    itinerary_place_count: int
    matched_content_ids: tuple[int, ...]
    unmatched_content_ids: tuple[int, ...]
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def overlap_ratio(self) -> float:
        if not self.itinerary_place_count:
            return 0.0
        return self.exact_match_count / self.itinerary_place_count
