"""Package quality helpers; direct execution builds the current final catalog."""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PATH = ROOT / "data/package_evaluation/generated_packages.100.json"
RAW_PATH = ROOT / "data/raw/korea_tour_openapi_jeju_places.csv"
OUTPUT_PATH = ROOT / "data/package_evaluation/final_packages.30.json"
DETAIL_PATH = ROOT / "data/package_evaluation/final_package_evaluation.30.json"
REPORT_PATH = ROOT / "data/package_evaluation/final_package_evaluation_criteria.md"

QUOTAS = {1: 3, 2: 9, 3: 9, 4: 5, 5: 4}
SCORE_WEIGHTS = {
    "route_naturalness": 25,
    "user_fit": 20,
    "schedule_realism": 15,
    "place_variety": 15,
    "title_description_alignment": 10,
    "season_fit": 5,
    "place_appeal": 5,
    "data_completeness": 5,
}

THEME_COMPATIBILITY = {
    "nature": {"nature", "trail"},
    "trail": {"trail", "nature"},
    "culture": {"culture", "history"},
    "history": {"history", "culture"},
    "experience": {"experience", "leisure", "theme_park"},
    "leisure": {"leisure", "experience"},
    "theme_park": {"theme_park", "experience"},
    "festival": {"festival"},
    "market_shopping": {"market_shopping", "culture"},
}

THEME_WORDS = {
    "nature": ("자연", "힐링", "숲", "바다", "오름"),
    "trail": ("걷기", "산책", "트레킹", "올레"),
    "culture": ("문화", "예술", "박물관", "미술관"),
    "history": ("역사", "유적", "전통"),
    "experience": ("체험", "아이", "가족"),
    "leisure": ("레저", "액티비티", "활동"),
    "theme_park": ("테마", "아이", "가족"),
    "festival": ("축제", "꽃", "계절"),
    "market_shopping": ("시장", "쇼핑", "기념품"),
}

PARTY_WORDS = {
    "children": ("아이", "어린이", "자녀", "가족"),
    "parents": ("부모", "효도", "어르신", "3대", "삼대"),
    "solo": ("혼자", "나홀로", "혼행", "여유"),
    "couple": ("연인", "커플", "부부", "친구", "둘이"),
    "group": ("가족", "친구", "단체", "함께"),
}

SUBTYPE_KEYWORDS = {
    "beach": ("해수욕장", "해변"),
    "oreum": ("오름",),
    "waterfall": ("폭포",),
    "flower": ("벚꽃", "유채", "동백", "수국", "꽃밭", "꽃길"),
    "island": ("우도", "마라도", "가파도", "비양도"),
    "road": ("도로",),
}

LONG_STAY_WORDS = (
    "한라산", "산행", "오름", "봉", "둘레길", "올레길", "숲길", "휴양림", "곶자왈",
    "우도", "마라도", "가파도", "비양도", "워터파크", "아쿠아플라넷",
)
ADULT_WORDS = ("러브랜드", "건강과 성", "술박물관")
HIGH_ACTIVITY_WORDS = ("카트", "레포츠", "카약", "승마", "워터")
EXCLUDED_WORDS = ("제주월드컵경기장", "제주 월드컵 경기장", "오일시장", "골프클럽", "골프 클럽")

SEASON_GROUPS = {
    "spring": ("벚꽃", "유채"),
    "summer": ("수국",),
    "autumn": ("억새",),
    "winter": ("동백", "감귤", "귤따기"),
}
SEASON_WORDS = {
    "spring": ("봄", "3월", "4월", "벚꽃", "유채"),
    "summer": ("여름", "6월", "7월", "8월", "수국"),
    "autumn": ("가을", "9월", "10월", "11월", "억새"),
    "winter": ("겨울", "11월", "12월", "1월", "동백", "감귤", "귤따기"),
}

ICONIC_WORDS = (
    "성산일출봉", "한라산", "우도", "협재해수욕장", "함덕해수욕장", "천지연폭포",
    "정방폭포", "천제연폭포", "섭지코지", "오설록", "카멜리아힐", "산굼부리",
    "비자림", "주상절리", "용두암", "아쿠아플라넷", "쇠소깍", "새별오름",
    "이호테우", "사려니숲길", "국립제주박물관", "제주민속촌", "제주돌문화공원",
)


@dataclass
class Evaluation:
    package: dict[str, Any]
    scores: dict[str, float]
    total_score: float
    hard_fail_reasons: list[str]
    metrics: dict[str, Any]
    party_group: str
    zone_signature: str
    place_ids: set[int]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def first(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = (row.get(key) or "").strip()
        if value:
            return value
    return ""


def load_raw() -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    with RAW_PATH.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if not row.get("contentid"):
                continue
            content_id = int(row["contentid"])
            mapx = first(row, "common_mapx", "mapx")
            mapy = first(row, "common_mapy", "mapy")
            result[content_id] = {
                "title": first(row, "common_title", "title"),
                "address": first(row, "common_addr1", "addr1"),
                "mapx": float(mapx) if mapx else None,
                "mapy": float(mapy) if mapy else None,
                "image": first(row, "common_firstimage", "firstimage"),
                "overview": first(row, "common_overview"),
            }
    return result


def haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    dlon, dlat = lon2 - lon1, lat2 - lat1
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(value))


def party_group(package: dict[str, Any]) -> str:
    parties = set(package["match_profile"]["party_types"])
    if "with_children" in parties:
        return "children"
    if parties.intersection({"with_parents", "three_generations"}):
        return "parents"
    if "solo" in parties:
        return "solo"
    if "non_family_group" in parties:
        return "group"
    return "couple"


def address_zone(address: str) -> str:
    if any(word in address for word in ("성산", "구좌", "조천")):
        return "동부"
    if any(word in address for word in ("애월", "한림", "한경")):
        return "서부"
    if any(word in address for word in ("중문", "안덕", "대정")):
        return "서남부"
    if any(word in address for word in ("남원", "표선")):
        return "동남부"
    if "서귀포" in address:
        return "서귀포"
    return "제주시"


def subtype(name: str) -> set[str]:
    return {kind for kind, words in SUBTYPE_KEYWORDS.items() if any(word in name for word in words)}


def category_compatible(category: str, themes: set[str]) -> bool:
    allowed = set().union(*(THEME_COMPATIBILITY.get(theme, {theme}) for theme in themes))
    return category in allowed


def score_route(day_distances: list[float], transfers: list[float]) -> float:
    average = sum(day_distances) / len(day_distances)
    maximum = max(day_distances)
    daily = clamp(20 - max(0, average - 8) * 0.65 - max(0, maximum - 20) * 0.3, 8, 20)
    if not transfers:
        continuity = 5.0
    else:
        average_transfer = sum(transfers) / len(transfers)
        continuity = clamp(5 - max(0, average_transfer - 12) * 0.12, 1, 5)
    return round(daily + continuity, 2)


def evaluate(package: dict[str, Any], raw: dict[int, dict[str, Any]]) -> Evaluation:
    all_places = [place for day in package["days"] for place in day["places"]]
    place_ids = {int(place["content_id"]) for place in all_places}
    group = party_group(package)
    themes = set(package["match_profile"]["themes"])
    hard_fail: list[str] = []
    day_distances: list[float] = []
    transfers: list[float] = []
    daily_totals: list[int] = []
    day_diversities: list[float] = []
    coordinates_complete = True

    previous_last: tuple[float, float] | None = None
    zones: set[str] = set()
    for day in package["days"]:
        places = day["places"]
        if len(places) not in (3, 4):
            hard_fail.append(f"day {day['day']}: 관광지 수가 3~4개가 아님")
        if len({p["content_id"] for p in places}) != len(places):
            hard_fail.append(f"day {day['day']}: 동일 content_id 중복")
        if [p["order"] for p in places] != list(range(1, len(places) + 1)):
            hard_fail.append(f"day {day['day']}: 방문 순서 오류")

        seen_types: set[str] = set()
        points: list[tuple[float, float]] = []
        for place in places:
            info = raw.get(int(place["content_id"]))
            if not info:
                hard_fail.append(f"TourAPI 미존재 content_id: {place['content_id']}")
                coordinates_complete = False
                continue
            zones.add(address_zone(info["address"]))
            if info["mapx"] is None or info["mapy"] is None:
                coordinates_complete = False
            else:
                points.append((info["mapx"], info["mapy"]))
            current_types = subtype(place["name"])
            if seen_types.intersection(current_types):
                hard_fail.append(f"day {day['day']}: 동일 관광유형 반복")
            seen_types.update(current_types)

        if len(points) == len(places):
            day_distances.append(sum(haversine(a, b) for a, b in zip(points, points[1:])))
            if previous_last is not None:
                transfers.append(haversine(previous_last, points[0]))
            previous_last = points[-1]
        else:
            day_distances.append(50.0)

        total_minutes = sum(int(place["stay_minutes"]) for place in places)
        daily_totals.append(total_minutes)
        day_diversities.append(len({p["category"] for p in places}) / len(places))
        if len(places) == 4 and any(
            int(place["stay_minutes"]) >= 120 or any(word in place["name"] for word in LONG_STAY_WORDS)
            for place in places
        ):
            hard_fail.append(f"day {day['day']}: 장기 체류 장소가 포함된 4개 일정")

    names = " ".join(place["name"] for place in all_places)
    text = f"{package['title']} {package['summary']}"
    if any(word in names for word in EXCLUDED_WORDS):
        hard_fail.append("제외 대상 관광지 포함")
    if group == "children" and any(word in names for word in ADULT_WORDS):
        hard_fail.append("아이 동반 코스에 성인 중심 장소 포함")
    if group == "parents" and any(word in names for word in HIGH_ACTIVITY_WORDS):
        hard_fail.append("부모님 동반 코스에 고강도 장소 포함")

    present_seasons = {
        season for season, words in SEASON_GROUPS.items() if any(word in names for word in words)
    }
    if "spring" in present_seasons and "winter" in present_seasons:
        hard_fail.append("봄꽃과 겨울 감귤·동백 일정 충돌")
    if max(day_distances) > 45:
        hard_fail.append("하루 직선 이동거리 45km 초과")

    route_score = score_route(day_distances, transfers)

    compatible_ratio = sum(category_compatible(p["category"], themes) for p in all_places) / len(all_places)
    party_safety = 5.0
    if group == "children" and any(word in names for word in HIGH_ACTIVITY_WORDS):
        party_safety = 4.0
    if group == "parents" and any(int(p["stay_minutes"]) >= 180 for p in all_places):
        party_safety = min(party_safety, 3.5)
    average_daily_minutes = sum(daily_totals) / len(daily_totals)
    paces = set(package["match_profile"].get("paces", []))
    pace_fit = 3.0
    if "relaxed" in paces and average_daily_minutes > 300:
        pace_fit = 1.5
    elif "active" in paces and average_daily_minutes < 180:
        pace_fit = 1.5
    user_score = round(12 * compatible_ratio + party_safety + pace_fit, 2)

    realism_ratios = []
    for total in daily_totals:
        realism_ratios.append(1.0 if 150 <= total <= 300 else 0.85 if 120 <= total <= 330 else 0.65)
    four_day_validity = 1.0 if not any("장기 체류 장소가 포함된 4개 일정" in x for x in hard_fail) else 0.0
    spread = max(daily_totals) - min(daily_totals)
    balance = 1.0 if spread <= 120 else 0.75 if spread <= 180 else 0.5
    realism_score = round(8 * sum(realism_ratios) / len(realism_ratios) + 4 * four_day_validity + 3 * balance, 2)

    daily_variety = sum(day_diversities) / len(day_diversities)
    target_categories = min(5, 2 + package["duration_days"])
    package_variety = min(1.0, len({p["category"] for p in all_places}) / target_categories)
    variety_score = round(10 * daily_variety + 5 * package_variety, 2)

    party_mentions = any(word in text for word in PARTY_WORDS[group])
    theme_mentions = sum(
        any(word in text for word in THEME_WORDS.get(theme, (theme,))) for theme in themes
    )
    party_alignment = 4.0 if party_mentions else 2.0
    theme_alignment = 3.0 * min(1.0, theme_mentions / min(2, max(1, len(themes))))
    zone_mentions = sum(zone in text for zone in zones if zone not in {"제주시", "서귀포"})
    region_alignment = 1.5 if "제주" in text else 0.5
    region_alignment += 1.5 if zone_mentions or "서귀포" in text else 0.75
    alignment_score = round(min(10, party_alignment + theme_alignment + region_alignment), 2)

    if not present_seasons:
        season_score = 5.0
    elif all(any(word in text for word in SEASON_WORDS[season]) for season in present_seasons):
        season_score = 5.0
    else:
        season_score = 2.5

    raw_infos = [raw.get(int(place["content_id"]), {}) for place in all_places]
    image_ratio = sum(bool(info.get("image")) for info in raw_infos) / len(raw_infos)
    overview_ratio = sum(bool(info.get("overview")) for info in raw_infos) / len(raw_infos)
    iconic_count = sum(any(word in p["name"] for word in ICONIC_WORDS) for p in all_places)
    iconic_target = max(1, math.ceil(package["duration_days"] / 2))
    appeal_score = round(2 * image_ratio + overview_ratio + 2 * min(1, iconic_count / iconic_target), 2)

    fields_complete = all(
        p.get("name") and p.get("category") and isinstance(p.get("stay_minutes"), int) and p["stay_minutes"] > 0
        for p in all_places
    )
    day_numbers_ok = [d["day"] for d in package["days"]] == list(range(1, package["duration_days"] + 1))
    id_complete = len(place_ids) == len(all_places) and all(pid in raw for pid in place_ids)
    metadata_ratio = sum(bool(info.get("overview") or info.get("image")) for info in raw_infos) / len(raw_infos)
    completeness_score = round(
        float(id_complete) + float(coordinates_complete) + float(fields_complete) + float(day_numbers_ok) + metadata_ratio,
        2,
    )

    scores = {
        "route_naturalness": route_score,
        "user_fit": user_score,
        "schedule_realism": realism_score,
        "place_variety": variety_score,
        "title_description_alignment": alignment_score,
        "season_fit": season_score,
        "place_appeal": appeal_score,
        "data_completeness": completeness_score,
    }
    total = round(sum(scores.values()), 2)
    metrics = {
        "average_daily_straight_distance_km": round(sum(day_distances) / len(day_distances), 2),
        "maximum_daily_straight_distance_km": round(max(day_distances), 2),
        "average_between_day_transfer_km": round(sum(transfers) / len(transfers), 2) if transfers else 0.0,
        "average_daily_stay_minutes": round(average_daily_minutes, 1),
        "daily_place_counts": [len(day["places"]) for day in package["days"]],
        "unique_category_count": len({p["category"] for p in all_places}),
        "theme_compatible_place_ratio": round(compatible_ratio, 3),
        "season_groups": sorted(present_seasons),
    }
    return Evaluation(
        package=package,
        scores=scores,
        total_score=total,
        hard_fail_reasons=sorted(set(hard_fail)),
        metrics=metrics,
        party_group=group,
        zone_signature="+".join(sorted(zones)),
        place_ids=place_ids,
    )


def jaccard(a: set[int], b: set[int]) -> float:
    return len(a & b) / len(a | b) if a or b else 0.0


def select(evaluations: list[Evaluation]) -> tuple[list[Evaluation], dict[str, dict[str, float]]]:
    eligible = [evaluation for evaluation in evaluations if not evaluation.hard_fail_reasons]
    selected: list[Evaluation] = []
    remaining = dict(QUOTAS)
    party_counts: Counter[str] = Counter()
    zone_counts: Counter[str] = Counter()
    selection_details: dict[str, dict[str, float]] = {}

    while sum(remaining.values()):
        candidates = [e for e in eligible if e not in selected and remaining[e.package["duration_days"]] > 0]
        if not candidates:
            raise RuntimeError(f"기간별 정원을 충족할 후보가 부족합니다: {remaining}")

        def adjusted(evaluation: Evaluation) -> tuple[float, float]:
            overlap = max((jaccard(evaluation.place_ids, x.place_ids) for x in selected), default=0.0)
            diversity_penalty = (
                party_counts[evaluation.party_group] * 0.8
                + zone_counts[evaluation.zone_signature] * 0.35
                + overlap * 8.0
            )
            return evaluation.total_score - diversity_penalty, evaluation.total_score

        choice = max(candidates, key=adjusted)
        adjusted_score, _ = adjusted(choice)
        overlap = max((jaccard(choice.place_ids, x.place_ids) for x in selected), default=0.0)
        selected.append(choice)
        remaining[choice.package["duration_days"]] -= 1
        party_counts[choice.party_group] += 1
        zone_counts[choice.zone_signature] += 1
        selection_details[choice.package["package_id"]] = {
            "diversity_adjusted_selection_score": round(adjusted_score, 2),
            "maximum_place_jaccard_with_previously_selected": round(overlap, 3),
        }

    selected.sort(key=lambda e: (-e.total_score, e.package["package_id"]))
    return selected, selection_details


def duration_label(days: int) -> str:
    return "당일" if days == 1 else f"{days - 1}박 {days}일"


def reason_text(evaluation: Evaluation) -> str:
    ranked = sorted(evaluation.scores.items(), key=lambda item: item[1] / SCORE_WEIGHTS[item[0]], reverse=True)
    labels = {
        "route_naturalness": "동선",
        "user_fit": "사용자 적합성",
        "schedule_realism": "일정 현실성",
        "place_variety": "관광지 다양성",
        "title_description_alignment": "제목·설명 일치",
        "season_fit": "계절 적합성",
        "place_appeal": "관광지 매력도",
        "data_completeness": "데이터 완성도",
    }
    return f"{labels[ranked[0][0]]}, {labels[ranked[1][0]]} 우수"


def write_outputs(
    evaluations: list[Evaluation], selected: list[Evaluation], selection_details: dict[str, dict[str, float]]
) -> None:
    selected_ids = {evaluation.package["package_id"] for evaluation in selected}
    final_packages = {
        "schema_version": "1.0",
        "selection_version": "1.0",
        "selected_at": date.today().isoformat(),
        "selection_policy": {
            "source_package_count": len(evaluations),
            "selected_package_count": len(selected),
            "duration_days_quota": {str(key): value for key, value in QUOTAS.items()},
            "score_weights": SCORE_WEIGHTS,
            "hard_fail_first": True,
            "diversity_adjustment": True,
        },
        "packages": [evaluation.package for evaluation in selected],
    }
    OUTPUT_PATH.write_text(json.dumps(final_packages, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    ranked_all = sorted(evaluations, key=lambda e: (-e.total_score, e.package["package_id"]))
    detail = {
        "schema_version": "1.0",
        "evaluated_at": date.today().isoformat(),
        "score_weights": SCORE_WEIGHTS,
        "duration_days_quota": {str(key): value for key, value in QUOTAS.items()},
        "summary": {
            "evaluated_package_count": len(evaluations),
            "hard_fail_package_count": sum(bool(e.hard_fail_reasons) for e in evaluations),
            "eligible_package_count": sum(not e.hard_fail_reasons for e in evaluations),
            "selected_package_count": len(selected),
            "selected_score_minimum": min(e.total_score for e in selected),
            "selected_score_average": round(sum(e.total_score for e in selected) / len(selected), 2),
            "selected_score_maximum": max(e.total_score for e in selected),
            "selected_duration_distribution": dict(sorted(Counter(e.package["duration_days"] for e in selected).items())),
            "selected_party_distribution": dict(sorted(Counter(e.party_group for e in selected).items())),
        },
        "evaluations": [
            {
                "overall_rank": rank,
                "selected": e.package["package_id"] in selected_ids,
                "package_id": e.package["package_id"],
                "title": e.package["title"],
                "duration_days": e.package["duration_days"],
                "duration_label": duration_label(e.package["duration_days"]),
                "party_group": e.party_group,
                "zone_signature": e.zone_signature,
                "total_score": e.total_score,
                "scores": e.scores,
                "metrics": e.metrics,
                "hard_fail_reasons": e.hard_fail_reasons,
                "selection": selection_details.get(e.package["package_id"]),
            }
            for rank, e in enumerate(ranked_all, 1)
        ],
    }
    DETAIL_PATH.write_text(json.dumps(detail, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    duration_rows = "\n".join(
        f"| {duration_label(days)} | {count}개 | {count / len(selected):.0%} |" for days, count in QUOTAS.items()
    )
    selected_rows = "\n".join(
        f"| {rank} | {e.package['package_id']} | {duration_label(e.package['duration_days'])} | "
        f"{e.party_group} | {e.zone_signature} | {e.total_score:.2f} | {reason_text(e)} |"
        for rank, e in enumerate(selected, 1)
    )
    report = f"""# 제주 가상 여행 패키지 최종 30개 평가·선정 기준

## 1. 선정 목적

100개 후보 중 실제 사용자에게 추천하기 적합하고, 이동 동선과 체류시간이 현실적인 패키지 30개를 선정했다. 품질점수만으로 자르면 비슷한 동반자·지역·장소 구성이 몰릴 수 있으므로, 규칙 위반 제거 → 100점 채점 → 기간별 정원 적용 → 구성 다양성 보정 순으로 선정했다.

## 2. 평가 배점

| 평가 항목 | 배점 | 세부 기준 |
|---|---:|---|
| 동선 자연스러움 | 25 | 일별 직선 이동거리 20점, 여러 날 일정의 전후 일자 연결 거리 5점 |
| 사용자 조건 적합성 | 20 | 테마와 관광지 유형 일치 12점, 동반자 안전성 5점, 여행 속도 적합성 3점 |
| 일정 현실성 | 15 | 일별 총 체류시간 8점, 4개 일정의 장기 체류 배제 4점, 날짜별 일정량 균형 3점 |
| 관광지 다양성 | 15 | 같은 날 관광유형 다양성 10점, 패키지 전체 카테고리 다양성 5점 |
| 제목·설명 일치도 | 10 | 동반자 표현 4점, 테마 표현 3점, 지역 표현 3점 |
| 계절 적합성 | 5 | 계절 관광지와 제목·설명의 계절 표현 일치 여부 |
| 장소 매력도 | 5 | TourAPI 이미지·소개 정보와 제주 대표 관광지 포함 정도 |
| 데이터 완성도 | 5 | content_id, 좌표, 필수 필드, 일자·방문 순서, TourAPI 메타데이터 |
| **합계** | **100** |  |

## 3. 자동 탈락 조건

- 하루 관광지가 3~4개가 아니거나 방문 순서가 잘못된 경우
- 같은 날 동일 관광지 또는 해수욕장·오름·폭포·꽃·섬·도로 유형이 반복된 경우
- TourAPI에 없는 `content_id` 또는 하루 직선 이동거리 45km 초과
- 4개 일정에 120분 이상 또는 산·오름·섬 등 장기 체류 장소가 포함된 경우
- 봄꽃과 겨울 감귤·동백처럼 계절이 충돌하는 경우
- 오일시장, 제주월드컵경기장, 제외 대상 골프 시설이 포함된 경우
- 아이 코스에 성인 중심 장소, 부모님 코스에 고강도 활동이 포함된 경우

## 4. 기간별 선발 비중

| 여행 기간 | 선발 수 | 비율 |
|---|---:|---:|
{duration_rows}

1박 2일과 2박 3일을 각각 9개씩 선발해 두 기간이 전체의 60%를 차지하도록 했다.

## 5. 다양성 보정 방식

자동 탈락을 통과한 후보를 대상으로 품질점수를 우선하되, 이미 선정된 패키지와 관광지 조합이 겹치거나 같은 동반자·지역 구성이 누적될수록 선택점수를 낮췄다. 관광지 조합 중복은 Jaccard 유사도로 계산했으며, 최종 JSON의 패키지 본문에는 평가용 필드를 섞지 않고 원래 스키마를 유지했다.

## 6. 최종 선정 결과

- 평가 후보: {len(evaluations)}개
- 자동 탈락: {sum(bool(e.hard_fail_reasons) for e in evaluations)}개
- 최종 선정: {len(selected)}개
- 선정 패키지 평균점수: {sum(e.total_score for e in selected) / len(selected):.2f}점
- 선정 패키지 점수 범위: {min(e.total_score for e in selected):.2f}~{max(e.total_score for e in selected):.2f}점

| 순위 | 패키지 ID | 기간 | 대표 동반자 | 주요 권역 | 점수 | 주요 선정 이유 |
|---:|---|---|---|---|---:|---|
{selected_rows}

## 7. 결과 파일

- `final_packages.30.json`: 서비스 적용용 최종 패키지 30개
- `final_package_evaluation.30.json`: 100개 전체의 항목별 점수, 탈락 사유, 선정 여부
- `final_package_evaluation_criteria.md`: 평가·선정 기준과 최종 목록
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    from select_complete_package_matrix import main as build_current_catalog

    raise SystemExit(build_current_catalog())


if __name__ == "__main__":
    main()
