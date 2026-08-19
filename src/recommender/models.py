from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# =========================================================
# 생성 일정
# =========================================================

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


# =========================================================
# 패키지 구성 장소
# =========================================================

@dataclass(frozen=True)
class PackageItem:
    day: int | None
    sequence: int | None
    item_type: str
    content_id: int

    # 패키지 추천 로직에서 사용하는 장소 카테고리
    place_categories: tuple[str, ...] = ()

    # 기존 코드에서 사용하던 정보
    title: str = ""
    stay_minutes: int | None = None
    longitude: float | None = None
    latitude: float | None = None


# =========================================================
# 패키지 후보
# =========================================================

@dataclass(frozen=True)
class PackageCandidate:
    package_id: str
    title: str
    summary: str
    region: str
    duration_days: int
    estimated_price: int

    # -----------------------------------------------------
    # 팀원 패키지 추천 로직에서 사용하는 값
    # -----------------------------------------------------

    companion_types: tuple[str, ...] = ()
    place_categories: tuple[str, ...] = ()

    # -----------------------------------------------------
    # 기존 우리 코드에서 사용하는 값
    # -----------------------------------------------------

    thumbnail_url: str = ""

    match_profile: dict[str, Any] = field(
        default_factory=dict
    )

    items: tuple[PackageItem, ...] = ()

    # repository / 추천 코드 호환용
    database_id: int | None = None

    # -----------------------------------------------------
    # 관광지 항목만 추출
    # -----------------------------------------------------

    @property
    def tourism_items(self) -> tuple[PackageItem, ...]:
        return tuple(
            item
            for item in self.items
            if item.item_type == "tourism"
        )


# =========================================================
# 추천 점수
# =========================================================

@dataclass(frozen=True)
class ScoreBreakdown:
    exact_overlap: float
    route_fit: float
    profile_fit: float
    nearby_fit: float
    total: float


# =========================================================
# 점수가 계산된 패키지
# =========================================================

@dataclass(frozen=True)
class ScoredPackage:
    package: PackageCandidate
    score: ScoreBreakdown

    exact_match_count: int
    itinerary_place_count: int

    matched_content_ids: tuple[int, ...]
    unmatched_content_ids: tuple[int, ...]

    evidence: dict[str, Any] = field(
        default_factory=dict
    )

    @property
    def overlap_ratio(self) -> float:
        if not self.itinerary_place_count:
            return 0.0

        return (
            self.exact_match_count
            / self.itinerary_place_count
        )