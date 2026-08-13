from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import MySQLConfig
from src.common.env import load_env_file
from src.recommender import (
    MySQLPackageRepository,
    PackageRecommendationService,
)

from apps.travel.kakao_route_service import get_kakao_day_route_path
from .pricing import calculate_custom_package_price


def recommend_packages(
    payload: dict[str, Any],
    *,
    top_k: int = 3,
) -> dict[str, Any]:
    """Run deterministic content-id matching against the travel database."""

    repository = MySQLPackageRepository(
        _travel_database_config()
    )

    service = PackageRecommendationService(
        repository
    )

    return service.recommend(
        payload,
        top_k=top_k,
    )


def recommend_package_comparison(
    payload: dict[str, Any],
    *,
    itinerary_id: int,
) -> dict[str, Any]:
    """Return one stored recommendation and a provisional custom quote."""

    # 자유일정 상품은 추천 패키지 조회와 별도로 먼저 생성
    custom_package = _build_custom_package(
        payload,
        itinerary_id=itinerary_id,
    )

    result = recommend_packages(
        payload,
        top_k=1,
    )

    recommendations = result.get("recommendations") or []

    if not recommendations:
        return {
            **result,
            "stored_package": None,
            "custom_package": custom_package,
        }

    stored_package = dict(recommendations[0])

    database_id = stored_package.get("database_id")

    if database_id is not None:
        stored_package["id"] = database_id

    # -------------------------------------------------
    # 추천 패키지 DAY별 실제 카카오 자동차 도로 경로
    # -------------------------------------------------
    days = stored_package.get("days") or []

    for day in days:
        items = [
            item
            for item in (day.get("items") or [])
            if (
                item.get("latitude") is not None
                and item.get("longitude") is not None
            )
        ]

        items.sort(
            key=lambda item: int(
                item.get("sequence") or 0
            )
        )

        day_path = []

        if len(items) >= 2:
            try:
                day_path = get_kakao_day_route_path(
                    items
                )

            except (ValueError, RuntimeError) as exc:
                print(
                    "[Kakao] 추천 패키지 경로 조회 실패:",
                    f"DAY {day.get('day')}",
                    exc,
                )
                day_path = []

        day["path"] = day_path

        print(
            "[Kakao] 추천 패키지 경로 생성:",
            f"DAY {day.get('day')}",
            f"{len(day_path)} points",
        )

    # 추천 패키지와 자유일정 연결
    custom_package["reference_package_id"] = (
        stored_package["package_id"]
    )

    return {
        **result,
        "recommendations": [
            stored_package
        ],
        "stored_package": stored_package,
        "custom_package": custom_package,
    }


def _build_custom_package(
    payload: dict[str, Any],
    *,
    itinerary_id: int,
) -> dict[str, Any]:
    itinerary = payload.get("itinerary") or {}
    condition = (
        payload.get("condition")
        or payload.get("conditions")
        or {}
    )
    hotel = itinerary.get("hotel") or {}

    duration_days = condition.get("duration_days")

    if duration_days is None:
        duration_days = len(
            itinerary.get("days") or []
        )

    try:
        duration_days = max(
            int(duration_days or 1),
            1,
        )
    except (TypeError, ValueError):
        duration_days = 1

    try:
        nights = max(
            int(
                hotel.get(
                    "nights",
                    duration_days - 1,
                )
            ),
            0,
        )
    except (TypeError, ValueError):
        nights = max(
            duration_days - 1,
            0,
        )

    quote = calculate_custom_package_price(
        nights,
        hotel.get("title"),
    )

    return {
        "product_type": "custom_itinerary",
        "itinerary_id": itinerary_id,
        "title": "내가 확정한 자유패키지",
        "reference_package_id": None,
        **quote.to_dict(),
        "is_provisional_quote": nights > 0,
    }


def _travel_database_config() -> MySQLConfig:
    """Keep recommendation reads separate from Django's account database."""

    _load_local_admin_env()

    host = (
        os.environ.get("TRAVEL_DB_HOST")
        or os.environ.get("MYSQL_HOST")
        or os.environ.get("MYSQL_ADMIN_HOST")
        or "127.0.0.1"
    )

    port = (
        os.environ.get("TRAVEL_DB_PORT")
        or os.environ.get("MYSQL_PORT")
        or os.environ.get("MYSQL_ADMIN_PORT")
        or "3306"
    )

    user = (
        os.environ.get("TRAVEL_DB_USER")
        or os.environ.get("MYSQL_USER")
        or os.environ.get("MYSQL_ADMIN_USER")
    )

    password = (
        os.environ.get("TRAVEL_DB_PASSWORD")
        or os.environ.get("MYSQL_PASSWORD")
        or os.environ.get("MYSQL_ADMIN_PASSWORD")
    )

    database = (
        os.environ.get("TRAVEL_DB_NAME")
        or os.environ.get("MYSQL_DATABASE")
    )

    missing = [
        name
        for name, value in {
            "MYSQL_USER/TRAVEL_DB_USER": user,
            "MYSQL_PASSWORD/TRAVEL_DB_PASSWORD": password,
            "MYSQL_DATABASE/TRAVEL_DB_NAME": database,
        }.items()
        if not value
    ]

    if missing:
        raise ValueError(
            "추천 DB 환경변수가 없습니다: "
            + ", ".join(missing)
        )

    try:
        parsed_port = int(port)

    except ValueError as exc:
        raise ValueError(
            "TRAVEL_DB_PORT 또는 MYSQL_PORT는 정수여야 합니다."
        ) from exc

    return MySQLConfig(
        host=host,
        port=parsed_port,
        user=str(user),
        password=str(password),
        database=str(database),
        connect_timeout=int(
            os.environ.get(
                "MYSQL_CONNECT_TIMEOUT",
                "10",
            )
        ),
    )


def _load_local_admin_env() -> None:
    configured = os.environ.get(
        "MYSQL_LOCAL_ADMIN_ENV"
    )

    if configured:
        load_env_file(configured)
        return

    load_env_file(
        PROJECT_ROOT.parent
        / ".mysql-local-admin.env"
    )