"""Run release checks against the final Jeju package catalog.

The validator is read-only. It checks catalog structure, TourAPI links, package
rules, duration/party coverage, season consistency, and route efficiency. It
writes both a machine-readable JSON result and a reviewer-friendly Markdown
report.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import os
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/package_evaluation/final_packages.50.json"
DEFAULT_RAW = ROOT / "data/raw/korea_tour_openapi_jeju_places.csv"
DEFAULT_JSON_REPORT = ROOT / "data/package_evaluation/final_package_validation.json"
DEFAULT_MD_REPORT = ROOT / "data/package_evaluation/final_package_validation.md"

EXPECTED_PACKAGE_COUNT = 50
EXPECTED_DURATION_COUNT = 10
PARTY_TYPES = (
    "with_children",
    "family_group",
    "non_family_two",
    "family_two",
    "non_family_group",
    "with_parents",
    "three_generations",
    "solo",
)
PARTY_KOREAN = {
    "with_children": "아이 동반",
    "family_group": "가족 단체",
    "non_family_two": "비가족 2인",
    "family_two": "가족 2인",
    "non_family_group": "비가족 단체",
    "with_parents": "부모님 동반",
    "three_generations": "3대 가족",
    "solo": "혼자 여행",
}
TOURISM_CONTENT_TYPES = {12, 14, 15, 28, 38}
RESTAURANT_CONTENT_TYPE = 39
HOTEL_CONTENT_TYPE = 32

SUBTYPE_KEYWORDS = {
    "해수욕장/해변": ("해수욕장", "해변"),
    "오름": ("오름",),
    "폭포": ("폭포",),
    "꽃길/꽃밭": ("벚꽃", "유채", "동백", "수국", "꽃밭", "꽃길"),
    "섬": ("우도", "마라도", "가파도", "비양도"),
    "도로": ("도로",),
}
SEASON_GROUPS = {
    "봄": ("벚꽃", "유채"),
    "여름": ("수국",),
    "가을": ("억새",),
    "겨울": ("동백", "감귤", "귤따기"),
}
SEASON_TEXT_WORDS = {
    "봄": ("봄", "3월", "4월", "벚꽃", "유채"),
    "여름": ("여름", "6월", "7월", "8월", "수국"),
    "가을": ("가을", "9월", "10월", "11월", "억새"),
    "겨울": ("겨울", "11월", "12월", "1월", "동백", "감귤", "귤따기"),
}
LONG_STAY_WORDS = (
    "한라산", "산행", "오름", "둘레길", "올레길", "숲길", "휴양림", "곶자왈",
    "우도", "마라도", "가파도", "비양도", "워터파크", "아쿠아플라넷",
)
EXCLUDED_ATTRACTION_WORDS = (
    "제주월드컵경기장", "제주 월드컵 경기장", "오일시장", "골프클럽", "골프 클럽",
)
NON_MEAL_NAME_WORDS = (
    "카페", "커피", "베이커리", "빵집", "다옥", "축협", "농협", "수협",
    "축산물플라자", "정육",
)
NON_MEAL_MENU_WORDS = (
    "그릭요거트", "팬케이크", "에그타르트", "벽돌빵", "피스타로쉐", "프리미엄 티", "수제차",
)
VERIFIED_NON_MEAL_IDS = {
    1823088, 2808238, 2864309, 2905340, 3037925,
    3057498, 3434312, 3492149, 4057215,
}
CAFE_CATEGORY = "A05020900"


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    message: str
    package_id: str | None = None
    day: int | None = None


def first(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = (row.get(key) or "").strip()
        if value:
            return value
    return ""


def load_raw(path: Path) -> dict[int, dict[str, Any]]:
    records: dict[int, dict[str, Any]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            content_id = (row.get("contentid") or "").strip()
            if not content_id.isdigit():
                continue
            mapx = first(row, "common_mapx", "mapx")
            mapy = first(row, "common_mapy", "mapy")
            records[int(content_id)] = {
                "title": first(row, "common_title", "title"),
                "content_type_id": int(first(row, "contenttypeid") or 0),
                "category": first(row, "common_cat3", "cat3"),
                "address": first(row, "common_addr1", "addr1"),
                "mapx": float(mapx) if mapx else None,
                "mapy": float(mapy) if mapy else None,
                "first_menu": first(row, "intro_firstmenu"),
                "treat_menu": first(row, "intro_treatmenu"),
            }
    return records


def haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    dlon, dlat = lon2 - lon1, lat2 - lat1
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(value))


def route_distance(points: Iterable[tuple[float, float]]) -> float:
    route = list(points)
    return sum(haversine(a, b) for a, b in zip(route, route[1:]))


def shortest_open_route(points: list[tuple[float, float]]) -> float:
    return min(route_distance(order) for order in itertools.permutations(points)) if len(points) > 1 else 0.0


def recursively_contains_key(value: Any, key_fragment: str) -> bool:
    if isinstance(value, dict):
        return any(key_fragment in str(key).lower() or recursively_contains_key(item, key_fragment) for key, item in value.items())
    if isinstance(value, list):
        return any(recursively_contains_key(item, key_fragment) for item in value)
    return False


def validate(payload: dict[str, Any], raw: dict[int, dict[str, Any]]) -> dict[str, Any]:
    issues: list[Issue] = []
    packages = payload.get("packages")
    if not isinstance(packages, list):
        packages = []
        issues.append(Issue("error", "catalog.packages_type", "packages가 배열이 아닙니다."))

    def add(severity: str, code: str, message: str, package_id: str | None = None, day: int | None = None) -> None:
        issues.append(Issue(severity, code, message, package_id, day))

    if len(packages) != EXPECTED_PACKAGE_COUNT:
        add("error", "catalog.package_count", f"패키지 수가 {EXPECTED_PACKAGE_COUNT}개가 아닙니다: {len(packages)}개")

    ids = [str(package.get("package_id", "")) for package in packages]
    titles = [str(package.get("title", "")) for package in packages]
    if len(ids) != len(set(ids)):
        add("error", "catalog.duplicate_id", "중복 package_id가 있습니다.")
    if len(titles) != len(set(titles)):
        add("error", "catalog.duplicate_title", "중복 패키지 제목이 있습니다.")
    if any(not title or len(title) > 24 for title in titles):
        add("error", "catalog.title_length", "빈 제목 또는 24자를 초과하는 제목이 있습니다.")

    duration_counts = Counter(int(package.get("duration_days", 0)) for package in packages)
    expected_distribution = Counter({duration: EXPECTED_DURATION_COUNT for duration in range(1, 6)})
    if duration_counts != expected_distribution:
        add("error", "coverage.duration_distribution", f"기간별 10개 구성이 아닙니다: {dict(duration_counts)}")

    coverage: dict[int, Counter[str]] = defaultdict(Counter)
    all_item_counts = Counter()
    route_metrics: list[dict[str, Any]] = []
    used_content_ids: set[int] = set()

    for package in packages:
        package_id = str(package.get("package_id", ""))
        duration = int(package.get("duration_days", 0))
        days = package.get("days", [])
        profile = package.get("match_profile", {})
        parties = profile.get("party_types", []) if isinstance(profile, dict) else []
        coverage[duration].update(parties)

        if recursively_contains_key(package, "transport"):
            add("error", "schema.transport_remaining", "이동수단 필드가 남아 있습니다.", package_id)
        if not 1 <= duration <= 5:
            add("error", "schema.duration_range", "duration_days가 1~5 범위가 아닙니다.", package_id)
        if len(days) != duration:
            add("error", "schema.day_count", f"days 개수({len(days)})와 duration_days({duration})가 다릅니다.", package_id)
        if [day.get("day") for day in days] != list(range(1, duration + 1)):
            add("error", "schema.day_sequence", "일차 번호가 1부터 순서대로 이어지지 않습니다.", package_id)
        if not isinstance(profile, dict) or not parties:
            add("error", "schema.match_profile", "동반자 조건이 없습니다.", package_id)
        unknown_parties = sorted(set(parties) - set(PARTY_TYPES))
        if unknown_parties:
            add("error", "schema.unknown_party", f"알 수 없는 동반자 조건: {unknown_parties}", package_id)
        price = package.get("estimated_price")
        if not isinstance(price, int) or price <= 0:
            add("error", "schema.price", "estimated_price가 양의 정수가 아닙니다.", package_id)

        hotel = package.get("hotel")
        if duration == 1 and hotel:
            add("error", "lodging.day_trip_hotel", "당일치기 패키지에 숙소가 있습니다.", package_id)
        if duration > 1 and not hotel:
            add("error", "lodging.overnight_missing", "숙박 패키지에 숙소가 없습니다.", package_id)
        if hotel:
            all_item_counts["hotel"] += 1
            hotel_id = int(hotel.get("content_id", 0))
            used_content_ids.add(hotel_id)
            info = raw.get(hotel_id)
            if not info:
                add("error", "tourapi.hotel_missing", f"숙소 content_id {hotel_id}가 원본에 없습니다.", package_id)
            elif info["content_type_id"] != HOTEL_CONTENT_TYPE:
                add("error", "tourapi.hotel_type", f"숙소가 TourAPI 숙박 유형(32)이 아닙니다: {hotel.get('name')}", package_id)

        package_tourism_ids: list[int] = []
        season_names: list[str] = []
        for day in days:
            day_no = int(day.get("day", 0))
            places = day.get("places", [])
            restaurant = day.get("restaurant")
            if not 3 <= len(places) <= 4:
                add("error", "schedule.place_count", f"관광지가 3~4개가 아닙니다: {len(places)}개", package_id, day_no)
            if [place.get("order") for place in places] != list(range(1, len(places) + 1)):
                add("error", "schedule.place_order", "관광지 order가 1부터 순서대로 이어지지 않습니다.", package_id, day_no)
            ids_in_day = [int(place.get("content_id", 0)) for place in places]
            if len(ids_in_day) != len(set(ids_in_day)):
                add("error", "schedule.duplicate_place_day", "같은 날 동일 content_id가 중복됩니다.", package_id, day_no)
            package_tourism_ids.extend(ids_in_day)
            all_item_counts["tourism"] += len(places)
            used_content_ids.update(ids_in_day)

            names = " ".join(str(place.get("name", "")) for place in places)
            season_names.append(names)
            for subtype, words in SUBTYPE_KEYWORDS.items():
                matched = [place.get("name", "") for place in places if any(word in str(place.get("name", "")) for word in words)]
                if len(matched) > 1:
                    add("error", "schedule.repeated_subtype", f"{subtype} 유형이 하루에 반복됩니다: {matched}", package_id, day_no)
            excluded = [word for word in EXCLUDED_ATTRACTION_WORDS if word in names]
            if excluded:
                add("error", "place.excluded", f"제외 관광지가 포함되어 있습니다: {excluded}", package_id, day_no)
            golf_places = [place.get("name", "") for place in places if "골프" in str(place.get("name", "")) and "렛츠런파크" not in str(place.get("name", ""))]
            if golf_places:
                add("error", "place.golf", f"골프 관련 관광지가 포함되어 있습니다: {golf_places}", package_id, day_no)
            if len(places) == 4 and any(
                int(place.get("stay_minutes", 0)) >= 120
                or any(word in str(place.get("name", "")) for word in LONG_STAY_WORDS)
                for place in places
            ):
                add("error", "schedule.long_stay_four_places", "장기 체류 장소가 포함된 날에 관광지가 4개입니다.", package_id, day_no)

            day_points: list[tuple[float, float]] = []
            full_route: list[tuple[float, float]] = []
            for place in places:
                content_id = int(place.get("content_id", 0))
                info = raw.get(content_id)
                if not info:
                    add("error", "tourapi.tourism_missing", f"관광지 content_id {content_id}가 원본에 없습니다.", package_id, day_no)
                    continue
                if info["content_type_id"] not in TOURISM_CONTENT_TYPES:
                    add("error", "tourapi.tourism_type", f"관광지가 허용된 TourAPI 유형이 아닙니다: {place.get('name')} ({info['content_type_id']})", package_id, day_no)
                if info["mapx"] is None or info["mapy"] is None:
                    add("error", "tourapi.coordinate_missing", f"관광지 좌표가 없습니다: {place.get('name')}", package_id, day_no)
                else:
                    day_points.append((info["mapx"], info["mapy"]))
                if not isinstance(place.get("stay_minutes"), int) or int(place.get("stay_minutes", 0)) <= 0:
                    add("error", "schedule.stay_minutes", f"체류시간이 올바르지 않습니다: {place.get('name')}", package_id, day_no)

            if not restaurant:
                add("error", "food.missing", "음식점이 없습니다.", package_id, day_no)
            else:
                all_item_counts["restaurant"] += 1
                restaurant_id = int(restaurant.get("content_id", 0))
                used_content_ids.add(restaurant_id)
                info = raw.get(restaurant_id)
                if not info:
                    add("error", "tourapi.restaurant_missing", f"음식점 content_id {restaurant_id}가 원본에 없습니다.", package_id, day_no)
                else:
                    if info["content_type_id"] != RESTAURANT_CONTENT_TYPE:
                        add("error", "tourapi.restaurant_type", f"음식점이 TourAPI 음식 유형(39)이 아닙니다: {restaurant.get('name')}", package_id, day_no)
                    menu = f"{info['first_menu']} {info['treat_menu']}"
                    name = str(restaurant.get("name", ""))
                    if info["category"] == CAFE_CATEGORY or any(word in name for word in NON_MEAL_NAME_WORDS) or any(word in info["first_menu"] for word in NON_MEAL_MENU_WORDS) or restaurant_id in VERIFIED_NON_MEAL_IDS:
                        add("error", "food.non_meal", f"식사 음식점이 아닌 후보입니다: {name} / {menu.strip()}", package_id, day_no)
                    after = int(restaurant.get("recommended_after_place_order", 0))
                    if not 1 <= after <= len(places):
                        add("error", "food.insert_order", f"음식점 삽입 순서가 잘못되었습니다: {after}", package_id, day_no)

            if len(day_points) == len(places):
                tourism_km = route_distance(day_points)
                full_route = list(day_points)
                if restaurant and raw.get(int(restaurant.get("content_id", 0))):
                    restaurant_info = raw[int(restaurant["content_id"])]
                    if restaurant_info["mapx"] is not None and restaurant_info["mapy"] is not None:
                        insert_at = int(restaurant.get("recommended_after_place_order", len(places)))
                        full_route.insert(insert_at, (restaurant_info["mapx"], restaurant_info["mapy"]))
                actual_km = route_distance(full_route)
                optimal_km = shortest_open_route(full_route)
                excess_km = max(0.0, actual_km - optimal_km)
                if tourism_km > 45:
                    add("warning", "route.long_day", f"관광지 기준 하루 직선 이동거리가 깁니다: {tourism_km:.1f}km", package_id, day_no)
                if excess_km > 5 and actual_km > optimal_km * 1.25:
                    add("warning", "route.inefficient_order", f"현재 순서가 최단 개방형 동선보다 {excess_km:.1f}km 깁니다.", package_id, day_no)
                route_metrics.append({
                    "package_id": package_id,
                    "day": day_no,
                    "tourism_route_km": round(tourism_km, 2),
                    "route_with_restaurant_km": round(actual_km, 2),
                    "shortest_open_route_km": round(optimal_km, 2),
                    "route_excess_km": round(excess_km, 2),
                })

        if len(package_tourism_ids) != len(set(package_tourism_ids)):
            duplicates = sorted(content_id for content_id, count in Counter(package_tourism_ids).items() if count > 1)
            add("error", "schedule.duplicate_place_package", f"패키지 내 관광지가 다른 일차에 중복됩니다: {duplicates}", package_id)

        all_names = " ".join(season_names)
        text = f"{package.get('title', '')} {package.get('summary', '')}"
        present_seasons = {season for season, words in SEASON_GROUPS.items() if any(word in all_names for word in words)}
        if "봄" in present_seasons and "겨울" in present_seasons:
            add("error", "season.spring_winter_conflict", "봄꽃과 겨울 동백·감귤 일정이 함께 포함됩니다.", package_id)
        for season in present_seasons:
            if not any(word in text for word in SEASON_TEXT_WORDS[season]):
                add("error", "season.description_missing", f"{season} 관광지가 있지만 제목·설명에 계절 안내가 없습니다.", package_id)

    missing_coverage: list[dict[str, Any]] = []
    for duration in range(1, 6):
        for party in PARTY_TYPES:
            if coverage[duration][party] < 1:
                missing_coverage.append({"duration_days": duration, "party_type": party})
    if missing_coverage:
        add("error", "coverage.duration_party", f"기간×동반자 조합이 누락되었습니다: {missing_coverage}")

    error_count = sum(issue.severity == "error" for issue in issues)
    warning_count = sum(issue.severity == "warning" for issue in issues)
    max_route = max(route_metrics, key=lambda item: item["route_with_restaurant_km"], default=None)
    max_excess = max(route_metrics, key=lambda item: item["route_excess_km"], default=None)
    checks = {
        "package_count": len(packages),
        "duration_distribution": {str(key): value for key, value in sorted(duration_counts.items())},
        "duration_party_coverage": f"{40 - len(missing_coverage)}/40",
        "unique_package_ids": len(set(ids)),
        "unique_titles": len(set(titles)),
        "maximum_title_length": max(map(len, titles), default=0),
        "item_counts": dict(all_item_counts),
        "unique_linked_content_ids": len(used_content_ids),
        "route_day_count": len(route_metrics),
        "maximum_route_with_restaurant": max_route,
        "maximum_route_excess": max_excess,
    }
    return {
        "validation_version": "1.0",
        "validated_at": date.today().isoformat(),
        "status": "PASS" if error_count == 0 else "FAIL",
        "summary": {"errors": error_count, "warnings": warning_count},
        "checks": checks,
        "coverage": {
            str(duration): {party: coverage[duration][party] for party in PARTY_TYPES}
            for duration in range(1, 6)
        },
        "issues": [asdict(issue) for issue in issues],
        "route_metrics": route_metrics,
    }


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def validate_database(result: dict[str, Any], env_file: Path) -> None:
    """Append read-only MySQL integrity checks to an existing result."""
    try:
        import mysql.connector
    except ImportError as exc:  # pragma: no cover - depends on local environment
        raise RuntimeError(
            "DB 검증에는 mysql-connector-python이 필요합니다. requirements.txt를 설치하세요."
        ) from exc

    env = {**os.environ, **load_env(env_file)}
    connection = mysql.connector.connect(
        host=env.get("MYSQL_HOST") or env.get("MYSQL_ADMIN_HOST") or "127.0.0.1",
        port=int(env.get("MYSQL_PORT") or env.get("MYSQL_ADMIN_PORT") or 3306),
        user=env.get("MYSQL_USER") or env.get("MYSQL_ADMIN_USER") or "root",
        password=env.get("MYSQL_PASSWORD") or env.get("MYSQL_ADMIN_PASSWORD") or "",
        database=env.get("TRAVEL_DB_NAME") or env.get("MYSQL_DATABASE") or "tour_recommender",
    )
    prefix = "VIRTUAL-JEJU-D%"
    scalar_queries = {
        "generated_packages": (
            "SELECT COUNT(*) FROM travel_packages WHERE package_id LIKE %s",
            (prefix,),
        ),
        "active_generated_packages": (
            "SELECT COUNT(*) FROM travel_packages WHERE package_id LIKE %s AND is_active=1",
            (prefix,),
        ),
        "missing_place_links": (
            "SELECT COUNT(*) FROM package_items pi "
            "JOIN travel_packages tp ON tp.id=pi.package_db_id "
            "LEFT JOIN places p ON p.content_id=pi.content_id "
            "WHERE tp.package_id LIKE %s AND p.content_id IS NULL",
            (prefix,),
        ),
        "restaurant_type_mismatch": (
            "SELECT COUNT(*) FROM package_items pi "
            "JOIN travel_packages tp ON tp.id=pi.package_db_id "
            "JOIN places p ON p.content_id=pi.content_id "
            "WHERE tp.package_id LIKE %s AND pi.item_type='restaurant' AND p.content_type_id<>39",
            (prefix,),
        ),
        "hotel_type_mismatch": (
            "SELECT COUNT(*) FROM package_items pi "
            "JOIN travel_packages tp ON tp.id=pi.package_db_id "
            "JOIN places p ON p.content_id=pi.content_id "
            "WHERE tp.package_id LIKE %s AND pi.item_type='hotel' AND p.content_type_id<>32",
            (prefix,),
        ),
        "daytrip_hotel_errors": (
            "SELECT COUNT(*) FROM package_items pi "
            "JOIN travel_packages tp ON tp.id=pi.package_db_id "
            "WHERE tp.package_id LIKE %s AND tp.duration_days=1 AND pi.item_type='hotel'",
            (prefix,),
        ),
        "overnight_missing_hotel": (
            "SELECT COUNT(*) FROM travel_packages tp "
            "LEFT JOIN package_items pi ON pi.package_db_id=tp.id AND pi.item_type='hotel' "
            "WHERE tp.package_id LIKE %s AND tp.duration_days>1 AND pi.id IS NULL",
            (prefix,),
        ),
        "daily_restaurant_count_errors": (
            "SELECT COUNT(*) FROM ("
            "SELECT tp.id, d.day_no, SUM(pi.item_type='restaurant') AS restaurant_count "
            "FROM travel_packages tp "
            "JOIN (SELECT 1 day_no UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5) d "
            "ON d.day_no<=tp.duration_days "
            "LEFT JOIN package_items pi ON pi.package_db_id=tp.id AND pi.day_no=d.day_no "
            "WHERE tp.package_id LIKE %s GROUP BY tp.id,d.day_no HAVING restaurant_count<>1"
            ") q",
            (prefix,),
        ),
    }
    db_checks: dict[str, Any] = {}
    try:
        cursor = connection.cursor()
        for name, (query, params) in scalar_queries.items():
            cursor.execute(query, params)
            db_checks[name] = int(cursor.fetchone()[0])
        cursor.execute(
            "SELECT pi.item_type, COUNT(*) FROM package_items pi "
            "JOIN travel_packages tp ON tp.id=pi.package_db_id "
            "WHERE tp.package_id LIKE %s GROUP BY pi.item_type",
            (prefix,),
        )
        db_checks["item_counts"] = {str(item_type): int(count) for item_type, count in cursor.fetchall()}
    finally:
        connection.close()

    expected_items = result["checks"]["item_counts"]
    expected = {
        "generated_packages": result["checks"]["package_count"],
        "active_generated_packages": result["checks"]["package_count"],
        "missing_place_links": 0,
        "restaurant_type_mismatch": 0,
        "hotel_type_mismatch": 0,
        "daytrip_hotel_errors": 0,
        "overnight_missing_hotel": 0,
        "daily_restaurant_count_errors": 0,
    }
    db_issues = []
    for name, expected_value in expected.items():
        if db_checks.get(name) != expected_value:
            db_issues.append(Issue("error", f"db.{name}", f"DB 값 {db_checks.get(name)} (기대값 {expected_value})"))
    if db_checks.get("item_counts") != expected_items:
        db_issues.append(Issue("error", "db.item_counts", f"DB 항목 수 {db_checks.get('item_counts')} (기대값 {expected_items})"))

    result["database"] = {
        "status": "PASS" if not db_issues else "FAIL",
        "checks": db_checks,
    }
    result["issues"].extend(asdict(issue) for issue in db_issues)
    result["summary"]["errors"] += len(db_issues)
    result["status"] = "PASS" if result["summary"]["errors"] == 0 else "FAIL"


def markdown(result: dict[str, Any]) -> str:
    checks = result["checks"]
    issues = result["issues"]
    coverage = result["coverage"]
    coverage_rows = [
        "| 여행 기간 | " + " | ".join(PARTY_KOREAN[party] for party in PARTY_TYPES) + " |",
        "|---|" + "---:|" * len(PARTY_TYPES),
    ]
    duration_labels = {1: "당일치기", 2: "1박 2일", 3: "2박 3일", 4: "3박 4일", 5: "4박 5일"}
    for duration in range(1, 6):
        coverage_rows.append(
            f"| {duration_labels[duration]} | "
            + " | ".join(str(coverage[str(duration)][party]) for party in PARTY_TYPES)
            + " |"
        )

    lines = [
        "# 제주 최종 패키지 50개 자동 검증 보고서",
        "",
        f"- 검증일: {result['validated_at']}",
        f"- 최종 판정: **{result['status']}**",
        f"- 오류: {result['summary']['errors']}건",
        f"- 주의: {result['summary']['warnings']}건",
        "",
        "## 핵심 결과",
        "",
        f"- 패키지: {checks['package_count']}개",
        f"- 기간별 분포: {checks['duration_distribution']}",
        f"- 기간×동반자 조합: {checks['duration_party_coverage']}",
        f"- 고유 패키지 ID/제목: {checks['unique_package_ids']}개 / {checks['unique_titles']}개",
        f"- 최대 제목 길이: {checks['maximum_title_length']}자",
        f"- 항목 수: 관광지 {checks['item_counts'].get('tourism', 0)}개, 음식점 {checks['item_counts'].get('restaurant', 0)}개, 숙소 {checks['item_counts'].get('hotel', 0)}개",
        f"- 연결된 고유 content_id: {checks['unique_linked_content_ids']}개",
        "",
        "## 기간별 동반자 포함 현황",
        "",
        *coverage_rows,
        "",
    ]
    if "database" in result:
        db = result["database"]
        db_checks = db["checks"]
        lines.extend([
            "## MySQL 적재 검증",
            "",
            f"- 판정: **{db['status']}**",
            f"- 활성 패키지: {db_checks.get('active_generated_packages', 0)}개",
            f"- 항목 수: {db_checks.get('item_counts', {})}",
            f"- 존재하지 않는 places 참조: {db_checks.get('missing_place_links', 0)}건",
            f"- 음식점/숙소 유형 오류: {db_checks.get('restaurant_type_mismatch', 0)}건 / {db_checks.get('hotel_type_mismatch', 0)}건",
            f"- 당일치기 숙소/숙박 일정 숙소 누락: {db_checks.get('daytrip_hotel_errors', 0)}건 / {db_checks.get('overnight_missing_hotel', 0)}건",
            f"- 일차별 음식점 수 오류: {db_checks.get('daily_restaurant_count_errors', 0)}건",
            "",
        ])
    lines.extend([
        "## 발견 사항",
        "",
    ])
    if not issues:
        lines.append("- 오류와 주의 항목이 없습니다.")
    else:
        for issue in issues:
            location = ""
            if issue["package_id"]:
                location += f" `{issue['package_id']}`"
            if issue["day"] is not None:
                location += f" {issue['day']}일차"
            lines.append(f"- **{issue['severity'].upper()}** `{issue['code']}`{location}: {issue['message']}")
    lines.extend([
        "",
        "## 판정 기준",
        "",
        "- ERROR가 1건이라도 있으면 FAIL입니다.",
        "- WARNING은 데이터 오류는 아니지만 지도에서 직접 확인할 동선 후보입니다.",
        "- 음식점은 TourAPI 음식점 유형, 카페 분류, 대표 메뉴, 상호명 제외어를 함께 검사합니다.",
        "- 동선은 관광지와 음식점을 포함한 현재 순서를 동일 장소의 최단 개방형 경로와 비교합니다.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--json-report", type=Path, default=DEFAULT_JSON_REPORT)
    parser.add_argument("--md-report", type=Path, default=DEFAULT_MD_REPORT)
    parser.add_argument("--env-file", type=Path, help="지정하면 로컬 MySQL도 읽기 전용 검증")
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    result = validate(payload, load_raw(args.raw))
    if args.env_file:
        validate_database(result, args.env_file)
    args.json_report.parent.mkdir(parents=True, exist_ok=True)
    args.json_report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    args.md_report.write_text(markdown(result), encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "summary": result["summary"],
        "checks": result["checks"],
        "json_report": str(args.json_report),
        "markdown_report": str(args.md_report),
    }, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
