"""Add one nearby restaurant per day and one route-centered hotel per package."""

from __future__ import annotations

import csv
import itertools
import json
import math
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PATH = ROOT / "data/package_evaluation/final_packages.50.json"
RAW_PATH = ROOT / "data/raw/korea_tour_openapi_jeju_places.csv"
REPORT_PATH = ROOT / "data/package_evaluation/final_package_enrichment_report.json"
PRICE_REPORT_PATH = ROOT / "data/package_evaluation/final_package_pricing_report.md"

FOOD_TYPE_ID = "39"
LODGING_TYPE_ID = "32"

CAFE_CATEGORY = "A05020900"
FOOD_EXCLUDE_WORDS = (
    "카페", "커피", "베이커리", "제과", "디저트", "도넛", "아이스크림",
    "티하우스", "찻집", "와인바", "펍",
)
FOOD_MENU_EXCLUDE_WORDS = (
    "밀크티", "레몬차", "커피", "에이드", "주스", "스무디", "빙수",
    "케이크", "아이스크림", "디저트", "베이커리", "쿠키", "휘낭시에",
    "소금빵", "까눌레", "아메리카노", "스페셜티",
)
NON_MEAL_NAME_WORDS = (
    "카페", "커피", "베이커리", "빵집", "다옥",
    "축협", "농협", "수협", "축산물플라자", "정육",
)
NON_MEAL_FIRST_MENU_WORDS = (
    "그릭요거트", "팬케이크", "에그타르트", "벽돌빵",
    "피스타로쉐", "프리미엄 티", "수제차",
)
VERIFIED_NON_MEAL_CONTENT_IDS = {
    1823088,  # 서귀포시축협 축산물플라자
    3037925,  # 스페이스제로 (카페)
    2905340,  # 살롱드라방 (카페)
    3492149,  # 모아시 (카페)
    3057498,  # 자드부팡 (카페)
    2808238,  # 청춘부부 (베이커리 카페)
    2864309,  # 오뚜기빵집
    4057215,  # 회수다옥 (티하우스)
    3434312,  # 연리지가든 (정육 판매 중심)
}
HOTEL_INCLUDE_WORDS = (
    "호텔", "리조트", "소노캄", "하얏트", "신라스테이", "메종글래드",
    "롯데", "켄싱턴", "라마다", "그랜드 조선", "해비치",
)
HOTEL_EXCLUDE_WORDS = (
    "골프", "펜션", "게스트", "민박", "캠핑", "야영", "모텔", "호스텔",
)
HOTEL_CATEGORY_CODES = {"B02010100", "B02010900"}
REGION_PATTERN = re.compile(
    r"제주 북동부|제주 남서부|제주 동부|제주 서부|제주시|서귀포"
)

DEFAULT_ADMISSION_PRICES = {
    "nature": 5_000,
    "trail": 5_000,
    "history": 5_000,
    "culture": 10_000,
    "experience": 15_000,
    "festival": 15_000,
    "theme_park": 25_000,
    "leisure": 30_000,
    "market_shopping": 0,
}
SIMPLE_MEAL_WORDS = (
    "국수", "우동", "라면", "김밥", "분식", "돈까스", "짜장", "짬뽕",
    "비빔밥", "막국수", "덮밥",
)
SPECIAL_MEAL_WORDS = (
    "흑돼지", "갈치", "전복", "해물", "활어회", "고등어", "옥돔", "문어",
)
LUXURY_HOTEL_WORDS = ("JW 메리어트", "제주신라호텔", "파르나스 호텔")
UPPER_HOTEL_WORDS = (
    "디아넥스", "라온호텔", "라헨느", "루체빌", "에코랜드 호텔", "엠버리조트",
    "제주 블랙스톤", "제주신화월드",
)


def first(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = (row.get(key) or "").strip()
        if value:
            return value
    return ""


def coordinates(row: dict[str, str]) -> tuple[float, float] | None:
    mapx = first(row, "common_mapx", "mapx")
    mapy = first(row, "common_mapy", "mapy")
    if not mapx or not mapy:
        return None
    return float(mapx), float(mapy)


def restaurant_exclusion_reason(record: dict[str, Any]) -> str | None:
    if record["content_id"] in VERIFIED_NON_MEAL_CONTENT_IDS:
        return "verified_non_meal_or_institutional_business"
    if record["category_code"] == CAFE_CATEGORY:
        return "tourapi_cafe_category"
    if any(word in record["name"] for word in FOOD_EXCLUDE_WORDS):
        return "cafe_or_dessert_name"
    if any(word in record["name"] for word in NON_MEAL_NAME_WORDS):
        return "non_meal_business_name"
    if not record["first_menu"]:
        return "missing_representative_menu"
    if any(word in record["first_menu"] for word in FOOD_MENU_EXCLUDE_WORDS):
        return "drink_or_dessert_representative_menu"
    if any(word in record["first_menu"] for word in NON_MEAL_FIRST_MENU_WORDS):
        return "brunch_or_bakery_representative_menu"
    return None


def load_raw() -> tuple[
    dict[int, dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    all_places: dict[int, dict[str, Any]] = {}
    restaurants: list[dict[str, Any]] = []
    hotels: list[dict[str, Any]] = []
    restaurant_exclusions: list[dict[str, Any]] = []
    with RAW_PATH.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if not row.get("contentid"):
                continue
            point = coordinates(row)
            record = {
                "content_id": int(row["contentid"]),
                "name": first(row, "common_title", "title"),
                "address": first(row, "common_addr1", "addr1"),
                "point": point,
                "content_type_id": first(row, "contenttypeid"),
                "category_code": first(row, "common_cat3", "cat3"),
                "first_menu": first(row, "intro_firstmenu"),
                "opening_time": first(row, "intro_opentimefood"),
                "rest_date": first(row, "intro_restdatefood"),
                "treat_menu": first(row, "intro_treatmenu"),
                "use_fee": first(row, "intro_usefee", "intro_usefeeleports"),
            }
            all_places[record["content_id"]] = record
            if point is None:
                continue
            if record["content_type_id"] == FOOD_TYPE_ID:
                reason = restaurant_exclusion_reason(record)
                if reason:
                    restaurant_exclusions.append(
                        {
                            "content_id": record["content_id"],
                            "name": record["name"],
                            "reason": reason,
                        }
                    )
                    continue
                restaurants.append(record)
            elif record["content_type_id"] == LODGING_TYPE_ID:
                if any(word in record["name"] for word in HOTEL_EXCLUDE_WORDS):
                    continue
                if not (
                    record["category_code"] in HOTEL_CATEGORY_CODES
                    or any(word in record["name"] for word in HOTEL_INCLUDE_WORDS)
                ):
                    continue
                hotels.append(record)
    return all_places, restaurants, hotels, restaurant_exclusions


def haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    dlon, dlat = lon2 - lon1, lat2 - lat1
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(value))


def restaurant_option(
    restaurant: dict[str, Any], day_points: list[tuple[float, float]]
) -> tuple[float, float, int]:
    """Return detour, nearest-place distance, and recommended preceding place order."""
    point = restaurant["point"]
    options = []
    for index, (left, right) in enumerate(itertools.pairwise(day_points), start=1):
        detour = haversine(left, point) + haversine(point, right) - haversine(left, right)
        options.append((detour, index))
    detour, after_order = min(options)
    nearest = min(haversine(point, tourism_point) for tourism_point in day_points)
    return detour, nearest, after_order


def choose_restaurant(
    candidates: list[dict[str, Any]], day_points: list[tuple[float, float]], used_ids: set[int]
) -> tuple[dict[str, Any], dict[str, Any]]:
    available = [candidate for candidate in candidates if candidate["content_id"] not in used_ids]
    ranked = sorted(
        (
            (*restaurant_option(candidate, day_points), candidate)
            for candidate in available
        ),
        key=lambda option: (option[0], option[1], option[3]["content_id"]),
    )
    detour, nearest, after_order, restaurant = ranked[0]
    return restaurant, {
        "recommended_after_place_order": after_order,
        "incremental_route_distance_km": round(detour, 2),
        "nearest_tourism_place_distance_km": round(nearest, 2),
    }


def choose_hotel(
    candidates: list[dict[str, Any]], day_points: list[list[tuple[float, float]]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    ranked = []
    for candidate in candidates:
        point = candidate["point"]
        endpoint_distances = [
            haversine(point, points[0]) + haversine(points[-1], point) for points in day_points
        ]
        total = sum(endpoint_distances)
        ranked.append((total, max(endpoint_distances), candidate, endpoint_distances))
    total, maximum, hotel, endpoint_distances = min(
        ranked, key=lambda option: (option[0], option[1], option[2]["content_id"])
    )
    return hotel, {
        "average_daily_start_end_distance_km": round(total / len(day_points), 2),
        "maximum_daily_start_end_distance_km": round(maximum, 2),
        "daily_start_end_distances_km": [round(value, 2) for value in endpoint_distances],
    }


def public_restaurant(record: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
    return {
        "content_id": record["content_id"],
        "name": record["name"],
        "category": "food",
        "stay_minutes": 60,
        "recommended_after_place_order": route["recommended_after_place_order"],
    }


def public_hotel(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "content_id": record["content_id"],
        "name": record["name"],
        "category": "lodging",
    }


def region_from_title(title: str) -> str:
    regions = list(dict.fromkeys(REGION_PATTERN.findall(title)))
    if not regions:
        raise ValueError(f"제목에서 권역을 찾지 못했습니다: {title}")
    return "·".join(regions)


def adult_admission_price(place: dict[str, Any], raw_place: dict[str, Any]) -> tuple[int, str]:
    fee_text = re.sub(r"<[^>]+>", " ", raw_place.get("use_fee", ""))
    fee_text = re.sub(r"\s+", " ", fee_text).strip()
    if fee_text.startswith("무료"):
        return 0, "tourapi_free"
    adult_match = re.search(
        r"(?:성인|어른|대인|일반)(?:\s*[,/]?\s*(?:대학생))?[^0-9]{0,20}([0-9][0-9,]*)\s*원",
        fee_text,
    )
    if adult_match:
        return int(adult_match.group(1).replace(",", "")), "tourapi_adult_fee"
    any_price = re.search(r"([0-9][0-9,]{2,})\s*원", fee_text)
    if any_price:
        return int(any_price.group(1).replace(",", "")), "tourapi_first_fee"
    return DEFAULT_ADMISSION_PRICES.get(place["category"], 10_000), "category_default"


def meal_price(raw_restaurant: dict[str, Any]) -> tuple[int, str]:
    menu_text = f"{raw_restaurant.get('name', '')} {raw_restaurant.get('first_menu', '')} {raw_restaurant.get('treat_menu', '')}"
    if any(word in menu_text for word in SPECIAL_MEAL_WORDS):
        return 30_000, "special_meal"
    if any(word in menu_text for word in SIMPLE_MEAL_WORDS):
        return 12_000, "simple_meal"
    return 18_000, "general_meal"


def hotel_room_price(hotel_name: str) -> tuple[int, str]:
    if any(word in hotel_name for word in LUXURY_HOTEL_WORDS):
        return 350_000, "luxury"
    if any(word in hotel_name for word in UPPER_HOTEL_WORDS):
        return 220_000, "upper"
    return 140_000, "standard"


def calculate_package_price(
    package: dict[str, Any], raw_places: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    admission_items = []
    meal_items = []
    for day in package["days"]:
        for place in day["places"]:
            amount, source = adult_admission_price(place, raw_places[int(place["content_id"])])
            admission_items.append(
                {"content_id": place["content_id"], "name": place["name"], "amount": amount, "source": source}
            )
        restaurant = day["restaurant"]
        amount, source = meal_price(raw_places[int(restaurant["content_id"])])
        meal_items.append(
            {"day": day["day"], "content_id": restaurant["content_id"], "name": restaurant["name"], "amount": amount, "source": source}
        )

    nights = max(0, package["duration_days"] - 1)
    lodging = {"nights": nights, "room_rate": 0, "tier": "none", "per_person_amount": 0}
    if nights:
        room_rate, tier = hotel_room_price(package["hotel"]["name"])
        lodging = {
            "hotel_name": package["hotel"]["name"],
            "nights": nights,
            "room_rate": room_rate,
            "tier": tier,
            "per_person_amount": room_rate * nights // 2,
        }

    admission_total = sum(item["amount"] for item in admission_items)
    meal_total = sum(item["amount"] for item in meal_items)
    direct_cost = admission_total + meal_total + lodging["per_person_amount"]
    final_amount = round(direct_cost * 1.2 / 1_000) * 1_000
    service_and_margin = final_amount - direct_cost
    return {
        "amount": final_amount,
        "admission_total": admission_total,
        "meal_total": meal_total,
        "lodging_total": lodging["per_person_amount"],
        "direct_cost": direct_cost,
        "service_and_margin": service_and_margin,
        "admission_items": admission_items,
        "meal_items": meal_items,
        "lodging": lodging,
    }


def won(amount: int) -> str:
    return f"{amount:,}원"


def duration_label(days: int) -> str:
    return "당일" if days == 1 else f"{days - 1}박 {days}일"


def write_pricing_report(pricing_entries: list[dict[str, Any]]) -> None:
    duration_groups: dict[int, list[int]] = {}
    for entry in pricing_entries:
        duration_groups.setdefault(entry["duration_days"], []).append(entry["pricing"]["amount"])
    duration_rows = "\n".join(
        f"| {duration_label(days)} | {len(amounts)}개 | {won(round(sum(amounts) / len(amounts) / 1000) * 1000)} | {won(min(amounts))} | {won(max(amounts))} |"
        for days, amounts in sorted(duration_groups.items())
    )
    package_rows = "\n".join(
        f"| {entry['package_id']} | {duration_label(entry['duration_days'])} | "
        f"{entry['region']} | {won(entry['pricing']['admission_total'])} | {won(entry['pricing']['meal_total'])} | "
        f"{won(entry['pricing']['lodging_total'])} | {won(entry['pricing']['direct_cost'])} | "
        f"{won(entry['pricing']['service_and_margin'])} | **{won(entry['pricing']['amount'])}** |"
        for entry in pricing_entries
    )
    all_amounts = [entry["pricing"]["amount"] for entry in pricing_entries]
    report = f"""# 제주 가상 여행 패키지 {len(pricing_entries)}개 가격 산정 리포트

## 1. 가격 표시 기준

- 최종 JSON의 `estimated_price`에는 총 예상가격 숫자만 저장한다.
- 가격 단위는 성인 1인, 호텔은 2인 1실 기준이다.
- 통화는 KRW이며 항공권, 현지 이동비, 개인 비용은 포함하지 않는다.
- 당일 패키지는 호텔을 포함하지 않으며 숙박비를 0원으로 계산한다.
- 실제 예약일이 없는 가상 상품이므로 실시간 판매가가 아닌 비교용 예상가격이다.

## 2. 계산식

```text
직접원가 = 관광지 입장료 + 일별 음식점 1회 + 1인 숙박비
운영비·마진 = 직접원가의 약 20%
최종가격 = 직접원가 × 1.2 후 1,000원 단위 반올림
```

## 3. 세부 기준

### 관광지 입장료

TourAPI `intro_usefee`에서 성인·어른·대인·일반 요금을 우선 추출했다. `무료`로 시작하는 장소는 0원으로 처리하고, 금액이 없으면 아래 카테고리 기준값을 사용했다.

| 카테고리 | 기본 1인 요금 |
|---|---:|
| 자연·산책·역사 | 5,000원 |
| 문화·박물관·미술관 | 10,000원 |
| 체험·축제 | 15,000원 |
| 테마파크 | 25,000원 |
| 레저 | 30,000원 |
| 시장·쇼핑 | 0원 |

### 음식점

TourAPI 대표 메뉴와 취급 메뉴를 기준으로 분류했다.

| 식사 유형 | 1인 요금 |
|---|---:|
| 국수·우동·분식·간단한 식사 | 12,000원 |
| 일반 식사 | 18,000원 |
| 흑돼지·갈치·전복·해산물 특식 | 30,000원 |

### 호텔

| 호텔 등급 | 객실 1박·2인 기준 | 1인 부담 |
|---|---:|---:|
| 일반 호텔 | 140,000원 | 70,000원 |
| 리조트·상급 호텔 | 220,000원 | 110,000원 |
| 특급 호텔 | 350,000원 | 175,000원 |

숙박비는 `객실 기준가격 × (여행 일수 - 1) ÷ 2`로 계산했다.

## 4. 기간별 가격 분포

| 기간 | 패키지 수 | 평균가격 | 최저가격 | 최고가격 |
|---|---:|---:|---:|---:|
{duration_rows}

전체 가격 범위는 {won(min(all_amounts))}~{won(max(all_amounts))}, 평균은 {won(round(sum(all_amounts) / len(all_amounts) / 1000) * 1000)}이다.

## 5. 패키지별 계산 결과

| 패키지 ID | 기간 | 권역 | 입장료 | 식비 | 숙박비 | 직접원가 | 운영비·마진 | 최종가격 |
|---|---|---|---:|---:|---:|---:|---:|---:|
{package_rows}

## 6. 해석 시 주의사항

- 관광지·음식점·호텔의 실제 가격은 방문 날짜, 주말, 성수기와 예약 조건에 따라 달라질 수 있다.
- TourAPI에 금액이 없는 장소는 동일한 카테고리 기준가격을 사용했다.
- 할인권, 어린이·경로 할인, 제주도민 할인은 반영하지 않았다.
- 서비스 적용 시에는 실제 예약 API 가격으로 교체하고, 현재 값은 추천·비교용 기준가로 사용하는 것이 적절하다.
"""
    PRICE_REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    document = json.loads(PACKAGE_PATH.read_text(encoding="utf-8"))
    previous_restaurants = {
        (package["package_id"], int(day["day"])): day["restaurant"]
        for package in document["packages"]
        for day in package["days"]
        if day.get("restaurant")
    }
    all_places, restaurant_candidates, hotel_candidates, restaurant_exclusions = load_raw()
    assignments = []
    pricing_entries = []

    for package in document["packages"]:
        package["match_profile"].pop("transports", None)
        package["region"] = package.get("region") or region_from_title(package["title"])
        package.pop("hotel", None)
        package_day_points: list[list[tuple[float, float]]] = []
        used_restaurants: set[int] = set()
        restaurant_reports = []

        for day in package["days"]:
            points = []
            for place in day["places"]:
                raw_place = all_places.get(int(place["content_id"]))
                if raw_place is None or raw_place["point"] is None:
                    raise ValueError(f"관광지 좌표 누락: {package['package_id']} / {place['content_id']}")
                points.append(raw_place["point"])
            package_day_points.append(points)
            restaurant, route = choose_restaurant(restaurant_candidates, points, used_restaurants)
            used_restaurants.add(restaurant["content_id"])
            day["restaurant"] = public_restaurant(restaurant, route)
            restaurant_reports.append(
                {
                    "day": day["day"],
                    "content_id": restaurant["content_id"],
                    "name": restaurant["name"],
                    "address": restaurant["address"],
                    "first_menu": restaurant["first_menu"],
                    "opening_time": restaurant["opening_time"],
                    "rest_date": restaurant["rest_date"],
                    **route,
                }
            )

        hotel_report = None
        if package["duration_days"] > 1:
            hotel, hotel_route = choose_hotel(hotel_candidates, package_day_points)
            package["hotel"] = public_hotel(hotel)
            hotel_report = {
                "content_id": hotel["content_id"],
                "name": hotel["name"],
                "address": hotel["address"],
                **hotel_route,
            }
        pricing = calculate_package_price(package, all_places)
        package["estimated_price"] = pricing["amount"]
        pricing_entries.append(
            {
                "package_id": package["package_id"],
                "title": package["title"],
                "duration_days": package["duration_days"],
                "region": package["region"],
                "pricing": pricing,
            }
        )
        assignments.append(
            {
                "package_id": package["package_id"],
                "region": package["region"],
                "hotel": hotel_report,
                "restaurants": restaurant_reports,
            }
        )

    document["selection_version"] = "1.2"
    document["food_lodging_enrichment"] = {
        "applied_at": date.today().isoformat(),
        "transport_removed": True,
        "restaurant_per_day": 1,
        "hotel_per_day_trip_package": 0,
        "hotel_per_overnight_package": 1,
        "restaurant_policy": "TourAPI 일반 음식점 중 날짜별 관광지 사이 추가 이동거리가 최소인 곳",
        "hotel_policy": "TourAPI 호텔·리조트 중 모든 날짜의 첫·마지막 관광지 왕복거리 합이 최소인 곳",
    }
    PACKAGE_PATH.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    restaurant_routes = [restaurant for assignment in assignments for restaurant in assignment["restaurants"]]
    hotel_routes = [assignment["hotel"] for assignment in assignments if assignment["hotel"] is not None]
    report = {
        "schema_version": "1.0",
        "evaluated_at": date.today().isoformat(),
        "source": "TourAPI raw CSV",
        "candidate_counts": {
            "restaurants_after_cafe_and_metadata_filter": len(restaurant_candidates),
            "restaurants_excluded_by_quality_filter": len(restaurant_exclusions),
            "hotels_and_resorts_after_filter": len(hotel_candidates),
        },
        "summary": {
            "package_count": len(document["packages"]),
            "restaurant_assignment_count": len(restaurant_routes),
            "hotel_assignment_count": len(hotel_routes),
            "unique_restaurant_count": len({x["content_id"] for x in restaurant_routes}),
            "unique_hotel_count": len({x["content_id"] for x in hotel_routes}),
            "average_restaurant_incremental_route_km": round(
                sum(x["incremental_route_distance_km"] for x in restaurant_routes) / len(restaurant_routes), 2
            ),
            "maximum_restaurant_incremental_route_km": max(
                x["incremental_route_distance_km"] for x in restaurant_routes
            ),
            "average_hotel_daily_start_end_distance_km": round(
                sum(x["average_daily_start_end_distance_km"] for x in hotel_routes) / len(hotel_routes), 2
            ),
            "maximum_hotel_daily_start_end_distance_km": max(
                x["maximum_daily_start_end_distance_km"] for x in hotel_routes
            ),
            "transport_field_remaining_count": sum(
                "transports" in package["match_profile"] for package in document["packages"]
            ),
            "day_trip_hotel_remaining_count": sum(
                package["duration_days"] == 1 and "hotel" in package for package in document["packages"]
            ),
            "overnight_package_missing_hotel_count": sum(
                package["duration_days"] > 1 and "hotel" not in package for package in document["packages"]
            ),
            "region_distribution": dict(
                sorted(Counter(package["region"] for package in document["packages"]).items())
            ),
        },
        "restaurant_quality_filter": {
            "verified_excluded_content_ids": sorted(VERIFIED_NON_MEAL_CONTENT_IDS),
            "excluded_candidates": restaurant_exclusions,
            "changed_assignments": [
                {
                    "package_id": assignment["package_id"],
                    "day": restaurant["day"],
                    "previous": previous_restaurants.get(
                        (assignment["package_id"], int(restaurant["day"]))
                    ),
                    "replacement": restaurant,
                }
                for assignment in assignments
                for restaurant in assignment["restaurants"]
                if previous_restaurants.get(
                    (assignment["package_id"], int(restaurant["day"]))
                )
                and int(
                    previous_restaurants[
                        (assignment["package_id"], int(restaurant["day"]))
                    ]["content_id"]
                ) != int(restaurant["content_id"])
            ],
        },
        "assignments": assignments,
    }
    write_pricing_report(pricing_entries)
    report["summary"]["minimum_estimated_price"] = min(entry["pricing"]["amount"] for entry in pricing_entries)
    report["summary"]["maximum_estimated_price"] = max(entry["pricing"]["amount"] for entry in pricing_entries)
    report["summary"]["average_estimated_price"] = round(
        sum(entry["pricing"]["amount"] for entry in pricing_entries) / len(pricing_entries) / 1_000
    ) * 1_000
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
