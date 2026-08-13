from __future__ import annotations

from typing import Any

from .models import ScoredPackage
from .normalization import normalize_itinerary, with_place_coordinates
from .package_repository import PackageRepository
from .profile_mapping import normalize_companion_types, normalize_condition_categories
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
                    "ranking_strategy": "weighted_total_score",
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
                "ranking_strategy": "weighted_total_then_overlap_tiebreaker",
                "score_weights": {
                    "tourism_match": 50,
                    "user_conditions": {
                        "total": 40,
                        "companion": 20,
                        "place_category": 15,
                        "season": 5,
                    },
                    "region_and_route": 10,
                },
            },
        }
    def find_reference_routes(
        self,
        condition: Any,
        *,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """AIHub fallback용 패키지 참고 경로를 조회한다.

        최종 일정으로 사용할 패키지를 추천하는 것이 아니라,
        패키지의 DAY/방문 순서를 이동 패턴 참고자료로 반환한다.
        """

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")

        # 여행 기간은 반드시 일치
        packages = self._repository.find_active_by_duration(
            condition.duration_days
        )

        if not packages:
            return []

        requested_companions = _condition_companions(condition)
        requested_categories = _condition_categories(condition)

        ranked: list[tuple[tuple[Any, ...], Any]] = []

        for package in packages:
            package_companions = set(
                normalize_companion_types(
                    package.companion_types
                )
            )

            package_categories = set(
                package.place_categories
            )

            # 동행 조건 일치 여부
            companion_match = bool(
                requested_companions & package_companions
            )

            # 사용자 선호 카테고리와 패키지 카테고리의 겹침 개수
            category_match_count = sum(
                1
                for category in requested_categories
                if category in package_categories
            )

            # 우선순위:
            # 1. 동행 조건
            # 2. 선호 카테고리
            # 3. 실제 관광지 수
            score = (
                int(companion_match),
                category_match_count,
                len(package.tourism_items),
            )

            ranked.append((score, package))

        ranked.sort(
            key=lambda row: (
                -row[0][0],
                -row[0][1],
                -row[0][2],
                row[1].package_id,
            )
        )

        selected = [
            package
            for _score, package in ranked[:top_k]
        ]

        return _package_route_rows(selected)



def _deterministic_reason(candidate: ScoredPackage) -> str:
    return (
        "내가 만든 일정의 여행 조건과 전반적인 구성이 비슷해 "
        "함께 비교해보기 좋은 패키지예요."
    )


def _serialize_recommendation(
    rank: int,
    candidate: ScoredPackage,
    reason: str,
) -> dict[str, Any]:
    ...
    package = candidate.package

    return {
        "rank": rank,
        "database_id": package.database_id,
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
            "tourism_match": candidate.score.exact_overlap,
            "user_conditions": candidate.score.profile_fit,
            "region_and_route": round(
                candidate.score.route_fit + candidate.score.nearby_fit,
                2,
            ),
            "exact_overlap": candidate.score.exact_overlap,
            "route_fit": candidate.score.route_fit,
            "profile_fit": candidate.score.profile_fit,
            "nearby_fit": candidate.score.nearby_fit,
            "total": candidate.score.total,
        },
        "evidence": candidate.evidence,
        "days": _serialize_days(package.items),
        "hotel": next(
            (
                _serialize_item(row)
                for row in package.items
                if row.item_type == "hotel"
            ),
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

def _condition_companions(condition: Any) -> set[str]:
    value = getattr(condition, "party_type", None)
    raw = getattr(value, "value", value)

    return set(
        normalize_companion_types((raw,))
    )


def _condition_categories(condition: Any) -> set[str]:
    preferences = getattr(
        condition,
        "preferred_visit_types",
        (),
    )

    raw = [
        getattr(item, "value", item)
        for item in preferences
    ]

    return normalize_condition_categories(raw)



def _package_route_rows(
    packages: list[Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for package in packages:
        for item in package.items:
            if item.day is None:
                continue

            if item.sequence is None:
                continue

            if item.item_type == "hotel":
                continue

            type_code = _item_visit_area_type(item)

            if type_code is None:
                continue

            rows.append(
                {
                    "travel_id": f"package:{package.package_id}",
                    "day_no": item.day,
                    "visit_order": item.sequence,
                    "visit_area_type_cd": type_code,
                    "place_name": item.title,
                    "content_id": item.content_id,
                    "package_id": package.package_id,
                }
            )

    return rows


def _item_visit_area_type(
    item: Any,
) -> str | None:
    for category in item.place_categories:
        category = str(category).strip().lower()

        if category == "food":
            return "11"

        if category == "cafe":
            return "11"

        if category == "shopping":
            return "10"

        if category == "activity":
            return "13"

    return None