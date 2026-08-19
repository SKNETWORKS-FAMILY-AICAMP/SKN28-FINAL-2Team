"""Expand short package days from three to four tourist attractions.

Rules:
- Correct the two spring packages that combined cherry blossoms with an
  unverified or autumn/winter citrus-picking experience.
- Prefer TourAPI ``intro_spendtime`` when it provides an explicit duration;
  otherwise retain the generator's type-based ``stay_minutes`` estimate.
- Add one nearby, short-stay attraction only when the existing three-place day
  is at most 210 minutes and contains no mountain/island/long-stay destination.
- Keep each day between three and four attractions and avoid repeated daily
  categories, beaches, waterfalls, oreums, flower sites, and place families.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import re
from collections import Counter
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

if __package__:
    from .optimize_package_routes import haversine_km, load_coordinates
else:
    from optimize_package_routes import haversine_km, load_coordinates


MAX_EXISTING_STAY_MINUTES = 210
MAX_ADDED_STAY_MINUTES = 60
MAX_INCREMENTAL_ROUTE_KM = 8.0
MAX_PLACE_USAGE = 5

SEASONAL_OR_UNSTABLE_KEYWORDS = (
    "감귤",
    "귤밭",
    "귤따기",
    "벚꽃",
    "유채꽃",
    "수국",
    "해바라기",
    "동백",
    "메밀",
    "꽃길",
    "꽃밭",
    "오일시장",
    "오일장",
)

LONG_STAY_KEYWORDS = (
    "한라산",
    "오름",
    "봉",
    "산행",
    "숲길",
    "둘레길",
    "휴양림",
    "곶자왈",
    "우도",
    "마라도",
    "가파도",
    "비양도",
    "서건도",
    "다려도",
    "워터파크",
    "아쿠아플라넷",
)

DAYTIME_EXCLUDED_KEYWORDS = ("불빛정원", "루나폴", "야간")
ADULT_KEYWORDS = ("러브랜드", "건강과 성", "술박물관")
HIGH_ACTIVITY_KEYWORDS = ("카트", "레포츠", "카약", "승마", "워터")

CATEGORY_THEME_COMPATIBILITY = {
    "nature": {"nature", "trail"},
    "trail": {"trail", "nature"},
    "culture": {"culture", "history"},
    "history": {"history", "culture"},
    "experience": {"experience", "leisure", "theme_park"},
    "leisure": {"leisure", "experience"},
    "theme_park": {"theme_park", "experience"},
    "festival": {"festival"},
    "market_shopping": {"market_shopping"},
}

TYPE_KEYWORDS = {
    "beach": ("해변", "해수욕장"),
    "waterfall": ("폭포",),
    "oreum": ("오름", "산봉", "산행", "봉"),
    "flower": ("벚꽃", "유채꽃", "수국", "해바라기", "동백", "꽃길", "꽃밭"),
    "road": ("해안도로", "드라이브", "도로"),
}

SEASONAL_REPLACEMENTS = {
    ("VIRTUAL-JEJU-000001", 2759624): 130461,  # 도련 감귤나무 숲 -> 국립제주박물관
    ("VIRTUAL-JEJU-000041", 3057412): 1544730,  # 보메와산감귤체험농장 -> 제주돌문화공원
}


def load_raw_rows(raw_csv: Path) -> dict[int, dict[str, str]]:
    with raw_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        return {
            int(row["contentid"]): row
            for row in csv.DictReader(handle)
            if row.get("contentid")
        }


def round_up_30(minutes: float) -> int:
    return max(30, int(math.ceil(minutes / 30.0) * 30))


def spend_time_minutes(raw: str) -> int | None:
    text = re.sub(r"<[^>]+>", " ", raw or "").strip()
    if not text:
        return None

    hour_range = re.search(r"(\d+(?:\.\d+)?)\s*~\s*(\d+(?:\.\d+)?)\s*시간", text)
    if hour_range:
        low, high = map(float, hour_range.groups())
        return round_up_30(((low + high) / 2) * 60)

    minute_range = re.search(r"(\d+)\s*~\s*(\d+)\s*분", text)
    if minute_range:
        low, high = map(int, minute_range.groups())
        return round_up_30((low + high) / 2)

    hours = re.search(r"(\d+(?:\.\d+)?)\s*시간", text)
    if hours:
        return round_up_30(float(hours.group(1)) * 60)

    minutes = re.search(r"(\d+)\s*분", text)
    if minutes:
        return round_up_30(float(minutes.group(1)))
    return None


def place_types(name: str) -> set[str]:
    return {
        label
        for label, keywords in TYPE_KEYWORDS.items()
        if any(keyword in name for keyword in keywords)
    }


def is_long_stay_place(place: dict[str, Any]) -> bool:
    return int(place["stay_minutes"]) >= 120 or any(
        keyword in place["name"] for keyword in LONG_STAY_KEYWORDS
    )


def normalized_name(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", name).lower()


def same_place_family(left: str, right: str) -> bool:
    a = normalized_name(left)
    b = normalized_name(right)
    if len(a) >= 4 and len(b) >= 4 and (a in b or b in a):
        return True
    special = ("이중섭", "성산일출봉", "산방산", "제주대", "렛츠런파크")
    return any(keyword in left and keyword in right for keyword in special)


def shortest_open_route_km(
    places: list[dict[str, Any]], coordinates: dict[int, tuple[float, float]]
) -> float:
    points = [coordinates[int(place["content_id"])] for place in places]
    return min(
        sum(
            haversine_km(points[left], points[right])
            for left, right in zip(order, order[1:])
        )
        for order in itertools.permutations(range(len(points)))
    )


def update_explicit_stay_minutes(
    packages: list[dict[str, Any]], raw_rows: dict[int, dict[str, str]]
) -> tuple[int, list[dict[str, Any]]]:
    changed_slots = 0
    evidence: dict[int, dict[str, Any]] = {}
    for package in packages:
        for day in package["days"]:
            for place in day["places"]:
                row = raw_rows[int(place["content_id"])]
                raw = row.get("intro_spendtime", "")
                parsed = spend_time_minutes(raw)
                if parsed is None:
                    continue
                evidence.setdefault(
                    int(place["content_id"]),
                    {
                        "content_id": int(place["content_id"]),
                        "name": place["name"],
                        "tourapi_spend_time": raw,
                        "applied_stay_minutes": parsed,
                    },
                )
                if int(place["stay_minutes"]) != parsed:
                    place["stay_minutes"] = parsed
                    changed_slots += 1
    return changed_slots, sorted(evidence.values(), key=lambda item: item["content_id"])


def build_canonical_places(packages: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    canonical: dict[int, dict[str, Any]] = {}
    for package in packages:
        for day in package["days"]:
            for place in day["places"]:
                canonical[int(place["content_id"])] = deepcopy(place)
    return canonical


def apply_seasonal_replacements(
    packages: list[dict[str, Any]], canonical: dict[int, dict[str, Any]]
) -> list[dict[str, Any]]:
    applied: list[dict[str, Any]] = []
    for package in packages:
        package_id = package["package_id"]
        for day in package["days"]:
            for index, place in enumerate(day["places"]):
                key = (package_id, int(place["content_id"]))
                replacement_id = SEASONAL_REPLACEMENTS.get(key)
                if replacement_id is None:
                    continue
                replacement = deepcopy(canonical[replacement_id])
                replacement["order"] = place["order"]
                day["places"][index] = replacement
                package["summary"] = package["summary"].replace(
                    place["name"], replacement["name"]
                )
                applied.append(
                    {
                        "package_id": package_id,
                        "day": day["day"],
                        "removed_content_id": int(place["content_id"]),
                        "removed_name": place["name"],
                        "added_content_id": replacement_id,
                        "added_name": replacement["name"],
                    }
                )
    return applied


def candidate_allowed(
    candidate: dict[str, Any],
    day_places: list[dict[str, Any]],
    package_ids: set[int],
    usage: Counter[int],
    package: dict[str, Any],
    raw_row: dict[str, str],
) -> bool:
    candidate_id = int(candidate["content_id"])
    if candidate_id in package_ids or usage[candidate_id] >= MAX_PLACE_USAGE:
        return False
    if raw_row.get("dataset") not in {"tourism", "leisure"}:
        return False
    if int(candidate["stay_minutes"]) > MAX_ADDED_STAY_MINUTES:
        return False
    if candidate["category"] in {"market_shopping", "festival"}:
        return False
    themes = set(package.get("match_profile", {}).get("themes", []))
    compatible_categories = set().union(
        *(CATEGORY_THEME_COMPATIBILITY.get(theme, {theme}) for theme in themes)
    )
    if candidate["category"] not in compatible_categories:
        return False
    if candidate["category"] in {place["category"] for place in day_places}:
        return False
    if any(keyword in candidate["name"] for keyword in SEASONAL_OR_UNSTABLE_KEYWORDS):
        return False
    if any(keyword in candidate["name"] for keyword in DAYTIME_EXCLUDED_KEYWORDS):
        return False
    party_types = set(package.get("match_profile", {}).get("party_types", []))
    if party_types.intersection({"with_children", "family_group", "family_two"}) and any(
        keyword in candidate["name"] for keyword in ADULT_KEYWORDS
    ):
        return False
    if "with_children" in party_types and any(
        keyword in candidate["name"] for keyword in HIGH_ACTIVITY_KEYWORDS
    ):
        return False
    if party_types.intersection({"with_parents", "three_generations"}) and any(
        keyword in candidate["name"] for keyword in HIGH_ACTIVITY_KEYWORDS
    ):
        return False
    if is_long_stay_place(candidate):
        return False
    existing_types = set().union(*(place_types(place["name"]) for place in day_places))
    if existing_types.intersection(place_types(candidate["name"])):
        return False
    if any(same_place_family(candidate["name"], place["name"]) for place in day_places):
        return False
    return True


def add_fourth_places(
    packages: list[dict[str, Any]],
    canonical: dict[int, dict[str, Any]],
    coordinates: dict[int, tuple[float, float]],
    raw_rows: dict[int, dict[str, str]],
) -> tuple[int, list[dict[str, Any]]]:
    usage: Counter[int] = Counter(
        int(place["content_id"])
        for package in packages
        for day in package["days"]
        for place in day["places"]
    )
    additions: list[dict[str, Any]] = []

    for package in packages:
        package_ids = {
            int(place["content_id"])
            for day in package["days"]
            for place in day["places"]
        }
        for day in package["days"]:
            places = day["places"]
            if len(places) != 3:
                continue
            before_stay = sum(int(place["stay_minutes"]) for place in places)
            if before_stay > MAX_EXISTING_STAY_MINUTES:
                continue
            if any(is_long_stay_place(place) for place in places):
                continue

            base_distance = shortest_open_route_km(places, coordinates)
            ranked: list[tuple[float, int, dict[str, Any], float]] = []
            for candidate_id, candidate in canonical.items():
                if not candidate_allowed(
                    candidate,
                    places,
                    package_ids,
                    usage,
                    package,
                    raw_rows[candidate_id],
                ):
                    continue
                combined = places + [candidate]
                new_distance = shortest_open_route_km(combined, coordinates)
                incremental = new_distance - base_distance
                if incremental > MAX_INCREMENTAL_ROUTE_KM:
                    continue
                score = incremental + usage[candidate_id] * 0.35
                ranked.append((score, candidate_id, candidate, incremental))

            if not ranked:
                continue
            _, candidate_id, selected, incremental = min(
                ranked, key=lambda item: (item[0], item[1])
            )
            new_place = deepcopy(selected)
            new_place["order"] = 4
            places.append(new_place)
            usage[candidate_id] += 1
            package_ids.add(candidate_id)
            additions.append(
                {
                    "package_id": package["package_id"],
                    "day": day["day"],
                    "content_id": candidate_id,
                    "name": new_place["name"],
                    "category": new_place["category"],
                    "stay_minutes": int(new_place["stay_minutes"]),
                    "daily_stay_before_minutes": before_stay,
                    "daily_stay_after_minutes": before_stay
                    + int(new_place["stay_minutes"]),
                    "incremental_straight_distance_km": round(incremental, 2),
                }
            )
    return len(additions), additions


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--packages",
        type=Path,
        default=Path("data/package_evaluation/generated_packages.100.json"),
    )
    parser.add_argument(
        "--raw-tourapi",
        type=Path,
        default=Path("data/raw/korea_tour_openapi_jeju_places.csv"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("data/package_evaluation/generation_report.100.json"),
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = json.loads(args.packages.read_text(encoding="utf-8"))
    packages = deepcopy(payload["packages"])
    raw_rows = load_raw_rows(args.raw_tourapi)
    coordinates = load_coordinates(args.raw_tourapi)

    stay_change_count, stay_evidence = update_explicit_stay_minutes(packages, raw_rows)
    canonical = build_canonical_places(packages)
    replacements = apply_seasonal_replacements(packages, canonical)
    added_count, additions = add_fourth_places(
        packages, canonical, coordinates, raw_rows
    )

    day_counts = Counter(
        len(day["places"]) for package in packages for day in package["days"]
    )
    stay_totals = [
        sum(int(place["stay_minutes"]) for place in day["places"])
        for package in packages
        for day in package["days"]
    ]
    usage = Counter(
        int(place["content_id"])
        for package in packages
        for day in package["days"]
        for place in day["places"]
    )
    metrics = {
        "stay_minutes_source": "TourAPI intro_spendtime 우선, 미기재 시 기존 장소유형 기준값 유지",
        "explicit_stay_time_place_count": len(stay_evidence),
        "stay_minutes_changed_slot_count": stay_change_count,
        "seasonal_replacement_count": len(replacements),
        "fourth_place_added_day_count": added_count,
        "places_per_day_distribution": dict(sorted(day_counts.items())),
        "total_place_slots": sum(count * days for count, days in day_counts.items()),
        "minimum_daily_stay_minutes": min(stay_totals),
        "average_daily_stay_minutes": round(sum(stay_totals) / len(stay_totals), 2),
        "maximum_daily_stay_minutes": max(stay_totals),
        "maximum_place_usage_count": max(usage.values()),
        "addition_policy": {
            "existing_daily_stay_max_minutes": MAX_EXISTING_STAY_MINUTES,
            "added_place_stay_max_minutes": MAX_ADDED_STAY_MINUTES,
            "incremental_straight_distance_max_km": MAX_INCREMENTAL_ROUTE_KM,
            "long_stay_days_remain_three_places": True,
        },
        "seasonal_replacements": replacements,
        "tourapi_explicit_stay_evidence": stay_evidence,
        "additions": additions,
    }

    print(json.dumps({key: value for key, value in metrics.items() if key not in {"tourapi_explicit_stay_evidence", "additions"}}, ensure_ascii=False, indent=2))
    if args.dry_run:
        return

    payload["packages"] = packages
    write_json(args.packages, payload)
    report = json.loads(args.report.read_text(encoding="utf-8"))
    report["generated_at"] = date.today().isoformat()
    report["tourism_places_per_day"] = {"minimum": 3, "maximum": 4}
    report["stay_and_daily_place_expansion"] = metrics
    report["total_place_slots"] = metrics["total_place_slots"]
    report.setdefault("generation_rules", {})["tourism_places_per_day"] = (
        "기본 3개, 기존 3개 관광지의 체류시간 합이 210분 이하인 짧은 일정만 최대 4개"
    )
    report.setdefault("validation", {})["maximum_place_usage_count"] = metrics[
        "maximum_place_usage_count"
    ]
    all_days = [day for package in packages for day in package["days"]]
    report["validation"]["places_per_day_errors"] = sum(
        not 3 <= len(day["places"]) <= 4 for day in all_days
    )
    report["validation"]["long_stay_four_place_day_errors"] = sum(
        len(day["places"]) == 4
        and any(is_long_stay_place(place) for place in day["places"])
        for day in all_days
    )
    report["validation"]["duplicate_content_id_within_day_errors"] = sum(
        len({place["content_id"] for place in day["places"]}) != len(day["places"])
        for day in all_days
    )
    write_json(args.report, report)


if __name__ == "__main__":
    main()
