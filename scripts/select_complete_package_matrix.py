"""Build 50 packages covering every duration and party-type combination."""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "data/package_evaluation/generated_packages.100.json"
OUTPUT_PATH = ROOT / "data/package_evaluation/final_packages.50.json"
REPORT_PATH = ROOT / "data/package_evaluation/final_package_coverage_report.md"

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
THEME_KOREAN = {
    "nature": "자연",
    "history": "역사",
    "culture": "문화",
    "market_shopping": "시장",
    "leisure": "레저",
    "theme_park": "테마",
    "trail": "산책",
    "festival": "축제",
    "experience": "체험",
}
REGION_PATTERN = re.compile(
    r"제주 북동부|제주 남서부|제주 동부|제주 서부|제주시|서귀포"
)
SEASON_RULES = (
    ("봄", ("벚꽃", "유채꽃"), "꽃 개화 시기는 날씨에 따라 달라질 수 있습니다."),
    ("여름", ("수국",), "수국은 주로 6~7월에 보기 좋습니다."),
    ("가을", ("억새",), "억새는 주로 가을에 보기 좋습니다."),
    ("겨울", ("동백", "감귤", "귤따기"), "동백과 감귤 체험은 주로 늦가을부터 겨울에 적합합니다."),
)


def duration_label(days: int) -> str:
    return "당일여행" if days == 1 else f"{days - 1}박{days}일"


def package_place_ids(package: dict[str, Any]) -> set[int]:
    return {
        int(place["content_id"])
        for day in package["days"]
        for place in day["places"]
    }


def jaccard(left: set[int], right: set[int]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def infer_region(package: dict[str, Any]) -> str:
    text = f"{package.get('title', '')} {package.get('summary', '')}"
    regions = list(dict.fromkeys(REGION_PATTERN.findall(text)))
    return "·".join(regions[:2]) if regions else "제주"


def compact_region(region: str) -> str:
    return (
        region.replace("제주 북동부", "북동부")
        .replace("제주 남서부", "남서부")
        .replace("제주 동부", "동부")
        .replace("제주 서부", "서부")
    )


def infer_season(package: dict[str, Any]) -> tuple[str, str]:
    text = " ".join(
        [package.get("title", ""), package.get("summary", "")]
        + [
            place.get("name", "")
            for day in package["days"]
            for place in day["places"]
        ]
    )
    for season, keywords, note in SEASON_RULES:
        if any(keyword in text for keyword in keywords):
            return season, note
    return "", ""


def audience_title(party_types: list[str]) -> str:
    parties = set(party_types)
    if "solo" in parties:
        if parties.intersection({"non_family_two", "family_two"}):
            return "혼자·둘이"
        return "혼자"
    if "with_children" in parties:
        return "아이와 가족"
    if parties.intersection({"with_parents", "three_generations"}):
        return "부모님과 가족"
    if "non_family_group" in parties:
        return "친구모임"
    if parties.intersection({"non_family_two", "family_two"}):
        return "둘이"
    return "가족단체"


def audience_description(party_types: list[str]) -> str:
    labels = [PARTY_KOREAN[party] for party in PARTY_TYPES if party in party_types]
    return "·".join(labels)


def rewrite_package(
    package: dict[str, Any],
    *,
    duration_index: int,
    add_solo: bool = False,
) -> dict[str, Any]:
    result = deepcopy(package)
    duration = int(result["duration_days"])
    party_types = list(dict.fromkeys(result["match_profile"].get("party_types", [])))
    if add_solo and "solo" not in party_types:
        party_types.append("solo")
    party_types = [party for party in PARTY_TYPES if party in party_types]
    result["match_profile"]["party_types"] = party_types
    result["match_profile"].pop("transports", None)
    result["package_id"] = f"VIRTUAL-JEJU-D{duration}-{duration_index:02d}"

    region = infer_region(result)
    season, season_note = infer_season(result)
    title_parts = [audience_title(party_types), compact_region(region)]
    if season:
        title_parts.append(season)
    title_parts.append(duration_label(duration))
    result["title"] = " ".join(title_parts)
    result["region"] = region

    place_names = [
        place["name"]
        for day in result["days"]
        for place in day["places"]
    ][:3]
    result["summary"] = (
        f"{audience_description(party_types)} 여행자에게 적합한 {region} "
        f"{duration_label(duration)} 패키지입니다. "
        f"{', '.join(place_names)} 등을 자연스러운 동선으로 구성했습니다."
    )
    if season_note:
        result["summary"] += f" {season_note}"
    return result


def select_duration_packages(
    pool: list[dict[str, Any]],
    evaluation_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    covered: set[str] = set()

    # Cover the rarest party types first. A selected package may cover several.
    party_counts = Counter(
        party
        for package in pool
        for party in package["match_profile"].get("party_types", [])
    )
    for party in sorted(PARTY_TYPES, key=lambda value: (party_counts[value], value)):
        if party in covered or party_counts[party] == 0:
            continue
        candidates = [
            package
            for package in pool
            if package["package_id"] not in selected_ids
            and party in package["match_profile"].get("party_types", [])
        ]
        if not candidates:
            continue
        choice = max(
            candidates,
            key=lambda package: (
                len(
                    set(package["match_profile"].get("party_types", []))
                    - covered
                )
                * 5
                + float(evaluation_by_id[package["package_id"]]["total_score"]),
                package["package_id"],
            ),
        )
        selected.append(choice)
        selected_ids.add(choice["package_id"])
        covered.update(choice["match_profile"].get("party_types", []))

    while len(selected) < 10:
        candidates = [
            package for package in pool if package["package_id"] not in selected_ids
        ]
        if not candidates:
            raise ValueError("not enough unique candidates to select 10 packages")

        def adjusted_score(package: dict[str, Any]) -> tuple[float, float, str]:
            score = float(evaluation_by_id[package["package_id"]]["total_score"])
            places = package_place_ids(package)
            overlap = max(
                (jaccard(places, package_place_ids(row)) for row in selected),
                default=0.0,
            )
            return score - overlap * 10.0, score, package["package_id"]

        choice = max(candidates, key=adjusted_score)
        selected.append(choice)
        selected_ids.add(choice["package_id"])
    return selected


def validate_catalog(packages: list[dict[str, Any]]) -> None:
    if len(packages) != 50:
        raise ValueError(f"expected 50 packages, got {len(packages)}")
    if len({package["package_id"] for package in packages}) != 50:
        raise ValueError("package IDs must be unique")
    duration_counts = Counter(int(package["duration_days"]) for package in packages)
    if duration_counts != Counter({duration: 10 for duration in range(1, 6)}):
        raise ValueError(f"duration distribution must be 10 each: {duration_counts}")
    missing = []
    for duration in range(1, 6):
        duration_packages = [
            package for package in packages if int(package["duration_days"]) == duration
        ]
        covered = {
            party
            for package in duration_packages
            for party in package["match_profile"].get("party_types", [])
        }
        for party in PARTY_TYPES:
            if party not in covered:
                missing.append((duration, party))
    if missing:
        raise ValueError(f"missing duration-party combinations: {missing}")
    if any(len(package["title"]) > 24 for package in packages):
        raise ValueError("package title exceeds 24 characters")
    if len({package["title"] for package in packages}) != len(packages):
        raise ValueError("package titles must be unique")


def make_titles_unique(packages: list[dict[str, Any]]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for package in packages:
        grouped[package["title"]].append(package)
    for duplicate_group in grouped.values():
        if len(duplicate_group) < 2:
            continue
        used_titles: set[str] = set()
        for index, package in enumerate(duplicate_group, start=1):
            duration = duration_label(int(package["duration_days"]))
            prefix = package["title"].removesuffix(duration).rstrip()
            themes = package["match_profile"].get("themes", [])
            theme = THEME_KOREAN.get(themes[-1], "코스") if themes else "코스"
            title = f"{prefix} {theme} {duration}"
            if title in used_titles:
                title = f"{prefix} {theme}{index} {duration}"
            package["title"] = title
            used_titles.add(title)


def coverage_counts(packages: list[dict[str, Any]]) -> dict[int, Counter[str]]:
    result: dict[int, Counter[str]] = defaultdict(Counter)
    for package in packages:
        duration = int(package["duration_days"])
        result[duration].update(package["match_profile"].get("party_types", []))
    return result


def write_report(packages: list[dict[str, Any]], source_ids: dict[str, str]) -> None:
    coverage = coverage_counts(packages)
    lines = [
        "| 여행기간 | " + " | ".join(PARTY_KOREAN[party] for party in PARTY_TYPES) + " |",
        "|---|" + "---:|" * len(PARTY_TYPES),
    ]
    for duration in range(1, 6):
        lines.append(
            f"| {duration_label(duration)} | "
            + " | ".join(str(coverage[duration][party]) for party in PARTY_TYPES)
            + " |"
        )
    party_totals = Counter(
        party
        for package in packages
        for party in package["match_profile"].get("party_types", [])
    )
    title_lengths = [len(package["title"]) for package in packages]
    solo_package = next(
        package for package in packages
        if package["duration_days"] == 1
        and "solo" in package["match_profile"]["party_types"]
    )
    report = f"""# 제주 패키지 50개 동반자 조합 보고서

## 구성 원칙

- 최종 패키지 50개, 여행기간별 10개씩 구성
- 한 패키지에 서로 어울리는 동반자 조건을 여러 개 지정할 수 있음
- 5개 여행기간 각각에서 AIHub 기반 동반자 유형 8종을 모두 최소 1회 이상 포함
- 기존 100개 후보 중 규칙 위반이 없는 고득점·저중복 일정을 우선 선택
- 제목은 동반자·지역·기간 중심으로 최대 24자 이내 구성

## 기간별 동반자 조건 포함 수

{chr(10).join(lines)}

모든 표의 값이 1 이상이므로 전체 40개 기간×동반자 조합을 충족한다.

## 전체 동반자 조건 분포

{chr(10).join(f'- {PARTY_KOREAN[party]}: {party_totals[party]}개' for party in PARTY_TYPES)}

## 보완 사항

- 기존 당일 후보에는 `solo`가 없어 `{solo_package['package_id']}`에 혼자 여행 조건을 추가했다.
- 해당 패키지의 원본은 `{source_ids[solo_package['package_id']]}`이며, 짧고 안전한 당일 동선을 선택했다.

## 검증 결과

- 패키지 수: 50개
- 기간별 패키지 수: 각 10개
- 충족한 기간×동반자 조합: 40/40
- 제목 길이: 최소 {min(title_lengths)}자, 최대 {max(title_lengths)}자, 평균 {sum(title_lengths) / len(title_lengths):.1f}자
- 중복 패키지 ID: 0개
- 중복 제목: {len(packages) - len({package['title'] for package in packages})}개
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> int:
    from select_top_packages import evaluate, load_raw

    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    raw = load_raw()
    evaluation_by_id = {}
    eligible_by_duration: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for package in source["packages"]:
        evaluation = evaluate(package, raw)
        evaluation_by_id[package["package_id"]] = {
            "total_score": evaluation.total_score,
            "hard_fail_reasons": evaluation.hard_fail_reasons,
        }
        if not evaluation.hard_fail_reasons:
            eligible_by_duration[int(package["duration_days"])].append(package)

    final_packages: list[dict[str, Any]] = []
    source_ids: dict[str, str] = {}
    for duration in range(1, 6):
        selected = select_duration_packages(
            eligible_by_duration[duration], evaluation_by_id
        )
        solo_target_id = None
        if duration == 1:
            solo_candidates = [
                package for package in selected
                if set(package["match_profile"].get("party_types", [])).intersection(
                    {"non_family_two", "family_two"}
                )
            ]
            solo_target = max(
                solo_candidates or selected,
                key=lambda package: float(
                    evaluation_by_id[package["package_id"]]["total_score"]
                ),
            )
            solo_target_id = solo_target["package_id"]

        selected.sort(key=lambda package: package["package_id"])
        for index, package in enumerate(selected, start=1):
            rewritten = rewrite_package(
                package,
                duration_index=index,
                add_solo=package["package_id"] == solo_target_id,
            )
            source_ids[rewritten["package_id"]] = package["package_id"]
            final_packages.append(rewritten)

    make_titles_unique(final_packages)
    validate_catalog(final_packages)
    document = {
        "schema_version": "1.0",
        "selection_version": "3.0",
        "selected_at": date.today().isoformat(),
        "selection_policy": {
            "source_package_count": len(source["packages"]),
            "selected_package_count": 50,
            "packages_per_duration": 10,
            "duration_party_complete_coverage": True,
            "duration_days": list(range(1, 6)),
            "party_types": list(PARTY_TYPES),
            "multiple_party_types_allowed": True,
            "maximum_title_length": 24,
        },
        "packages": final_packages,
    }
    OUTPUT_PATH.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_report(final_packages, source_ids)
    coverage = coverage_counts(final_packages)
    print(
        json.dumps(
            {
                "selected": len(final_packages),
                "duration_distribution": dict(
                    Counter(package["duration_days"] for package in final_packages)
                ),
                "covered_combinations": sum(
                    coverage[duration][party] > 0
                    for duration in range(1, 6)
                    for party in PARTY_TYPES
                ),
                "maximum_title_length": max(
                    len(package["title"]) for package in final_packages
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
