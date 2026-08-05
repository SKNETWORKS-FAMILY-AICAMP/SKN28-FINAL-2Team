from __future__ import annotations

from typing import Any

from .models import ScoredPackage
from .normalization import normalize_itinerary, with_place_coordinates
from .package_repository import PackageRepository
from .scoring import deterministic_sort_key, score_package


class PackageRecommendationService:
    def __init__(
        self,
        repository: PackageRepository,
        *,
        shortlist_size: int = 8,
    ) -> None:
        if shortlist_size <= 0:
            raise ValueError("shortlist_size must be greater than zero")
        self._repository = repository
        self._shortlist_size = shortlist_size

    def recommend(self, payload: dict[str, Any], *, top_k: int = 3) -> dict[str, Any]:
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")
        itinerary = normalize_itinerary(payload)
        place_rows = self._repository.get_places(
            [row.content_id for row in itinerary.tourism_stops]
        )
        itinerary = with_place_coordinates(itinerary, place_rows)
        packages = self._repository.find_active_by_duration(itinerary.duration_days)
        if not packages:
            return {
                "status": "no_candidates",
                "recommendations": [],
                "meta": {
                    "duration_days": itinerary.duration_days,
                    "candidate_count": 0,
                    "ranking_strategy": "exact_content_id_first",
                },
            }

        scored = sorted(
            (score_package(itinerary, package) for package in packages),
            key=deterministic_sort_key,
        )
        shortlist = scored[: max(top_k, self._shortlist_size)]
        selected = shortlist[:top_k]
        return {
            "status": "completed",
            "recommendations": [
                _serialize_recommendation(index, row, _deterministic_reason(row))
                for index, row in enumerate(selected, start=1)
            ],
            "meta": {
                "duration_days": itinerary.duration_days,
                "itinerary_tourism_place_count": len(
                    {row.content_id for row in itinerary.tourism_stops}
                ),
                "candidate_count": len(scored),
                "shortlist_count": len(shortlist),
                "ranking_strategy": "exact_content_id_first_then_route_profile_nearby",
                "score_weights": {
                    "exact_overlap": 70,
                    "same_day_and_order": 15,
                    "user_profile": 10,
                    "nearby_places": 5,
                },
            },
        }


def _deterministic_reason(candidate: ScoredPackage) -> str:
    matched = candidate.exact_match_count
    total = candidate.itinerary_place_count
    if matched:
        names = [
            item.title
            for item in candidate.package.tourism_items
            if item.content_id in candidate.matched_content_ids
        ][:3]
        place_text = ", ".join(names) if names else "일정 관광지"
        return (
            f"일정 관광지 {total}곳 중 {matched}곳({place_text})이 정확히 겹치고, "
            f"동선·사용자 조건을 포함한 점수는 {candidate.score.total:.2f}점입니다."
        )
    return (
        "정확히 겹치는 관광지는 없지만 사용자 조건과 인접 관광지 근거를 "
        f"반영한 점수가 {candidate.score.total:.2f}점입니다."
    )


def _serialize_recommendation(
    rank: int, candidate: ScoredPackage, reason: str
) -> dict[str, Any]:
    package = candidate.package
    return {
        "rank": rank,
        "package_id": package.package_id,
        "title": package.title,
        "summary": package.summary,
        "region": package.region,
        "duration_days": package.duration_days,
        "estimated_price": package.estimated_price,
        "reason": reason,
        "exact_match_count": candidate.exact_match_count,
        "itinerary_place_count": candidate.itinerary_place_count,
        "overlap_ratio": round(candidate.overlap_ratio, 4),
        "matched_content_ids": list(candidate.matched_content_ids),
        "unmatched_content_ids": list(candidate.unmatched_content_ids),
        "score": {
            "exact_overlap": candidate.score.exact_overlap,
            "route_fit": candidate.score.route_fit,
            "profile_fit": candidate.score.profile_fit,
            "nearby_fit": candidate.score.nearby_fit,
            "total": candidate.score.total,
        },
        "evidence": candidate.evidence,
        "days": _serialize_days(package.items),
        "hotel": next(
            (_serialize_item(row) for row in package.items if row.item_type == "hotel"),
            None,
        ),
    }


def _serialize_days(items: tuple[Any, ...]) -> list[dict[str, Any]]:
    day_numbers = sorted({row.day for row in items if row.day is not None})
    return [
        {
            "day": day,
            "items": [
                _serialize_item(row)
                for row in items
                if row.day == day and row.item_type != "hotel"
            ],
        }
        for day in day_numbers
    ]


def _serialize_item(item: Any) -> dict[str, Any]:
    return {
        "sequence": item.sequence,
        "item_type": item.item_type,
        "content_id": item.content_id,
        "title": item.title,
        "stay_minutes": item.stay_minutes,
        "longitude": item.longitude,
        "latitude": item.latitude,
    }
