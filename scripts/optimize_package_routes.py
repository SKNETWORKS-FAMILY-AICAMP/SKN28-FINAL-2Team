"""Optimize the visit order of each three- or four-place package day.

The package generator fixes the places assigned to a day.  This script
keeps that composition intact and changes only their visit order.  For every
day it evaluates all permutations, keeps the shortest open path, and then
chooses its forward/reverse direction with a package-level dynamic program.
The direction optimizer uses the previous/next day and Jeju Airport as the
first/last package anchor, so multi-day packages progress through the island
without unnecessary reversals.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable


EARTH_RADIUS_KM = 6371.0088
JEJU_AIRPORT = (33.5104135, 126.4913534)  # latitude, longitude
EPSILON = 1e-9


@dataclass(frozen=True)
class RouteOption:
    order: tuple[int, ...]
    internal_km: float
    start: tuple[float, float]
    end: tuple[float, float]


def haversine_km(
    left: tuple[float, float], right: tuple[float, float]
) -> float:
    lat1, lon1 = map(math.radians, left)
    lat2, lon2 = map(math.radians, right)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    value = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(value))


def load_coordinates(raw_csv: Path) -> dict[int, tuple[float, float]]:
    coordinates: dict[int, tuple[float, float]] = {}
    with raw_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            content_id = (row.get("contentid") or "").strip()
            longitude = (row.get("mapx") or "").strip()
            latitude = (row.get("mapy") or "").strip()
            if not content_id or not longitude or not latitude:
                continue
            coordinates[int(content_id)] = (float(latitude), float(longitude))
    return coordinates


def route_distance(
    places: list[dict[str, Any]],
    coordinates: dict[int, tuple[float, float]],
) -> float:
    points = [coordinates[int(place["content_id"])] for place in places]
    return sum(haversine_km(left, right) for left, right in zip(points, points[1:]))


def shortest_day_options(
    places: list[dict[str, Any]],
    coordinates: dict[int, tuple[float, float]],
) -> list[RouteOption]:
    if len(places) not in (3, 4):
        raise ValueError(f"Expected three or four places, received {len(places)}")

    points = [coordinates[int(place["content_id"])] for place in places]
    candidates: list[RouteOption] = []
    for order in itertools.permutations(range(len(points))):
        ordered_points = [points[index] for index in order]
        candidates.append(
            RouteOption(
                order=order,
                internal_km=sum(
                    haversine_km(left, right)
                    for left, right in zip(ordered_points, ordered_points[1:])
                ),
                start=ordered_points[0],
                end=ordered_points[-1],
            )
        )

    minimum = min(option.internal_km for option in candidates)
    shortest = [
        option for option in candidates if abs(option.internal_km - minimum) <= EPSILON
    ]

    # A shortest open path normally has two reverse orientations.  Keep
    # deterministic ordering for exact coordinate ties.
    shortest.sort(key=lambda option: option.order)
    return shortest


def choose_package_options(day_options: list[list[RouteOption]]) -> list[RouteOption]:
    """Choose route directions while keeping every day internally shortest."""

    if not day_options:
        return []

    # dp[day][option] = (cost, previous option index)
    costs: list[list[tuple[float, int | None]]] = []
    first_costs = [
        (haversine_km(JEJU_AIRPORT, option.start) + option.internal_km, None)
        for option in day_options[0]
    ]
    costs.append(first_costs)

    for day_index in range(1, len(day_options)):
        current_costs: list[tuple[float, int | None]] = []
        for option in day_options[day_index]:
            alternatives = []
            for previous_index, previous in enumerate(day_options[day_index - 1]):
                previous_cost = costs[day_index - 1][previous_index][0]
                transition = haversine_km(previous.end, option.start)
                alternatives.append(
                    (previous_cost + transition + option.internal_km, previous_index)
                )
            current_costs.append(min(alternatives, key=lambda item: (item[0], item[1])))
        costs.append(current_costs)

    last_day_index = len(day_options) - 1
    final_candidates = [
        (
            costs[last_day_index][option_index][0]
            + haversine_km(option.end, JEJU_AIRPORT),
            option_index,
        )
        for option_index, option in enumerate(day_options[last_day_index])
    ]
    _, selected_index = min(final_candidates, key=lambda item: (item[0], item[1]))

    selected: list[RouteOption] = []
    for day_index in range(last_day_index, -1, -1):
        selected.append(day_options[day_index][selected_index])
        previous_index = costs[day_index][selected_index][1]
        if previous_index is None:
            break
        selected_index = previous_index
    selected.reverse()
    return selected


def package_route_distance(
    package: dict[str, Any], coordinates: dict[int, tuple[float, float]]
) -> float:
    flattened = [
        coordinates[int(place["content_id"])]
        for day in package["days"]
        for place in day["places"]
    ]
    if not flattened:
        return 0.0
    total = haversine_km(JEJU_AIRPORT, flattened[0])
    total += sum(
        haversine_km(left, right) for left, right in zip(flattened, flattened[1:])
    )
    total += haversine_km(flattened[-1], JEJU_AIRPORT)
    return total


def optimize_packages(
    packages: list[dict[str, Any]],
    coordinates: dict[int, tuple[float, float]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    optimized = deepcopy(packages)
    used_ids = {
        int(place["content_id"])
        for package in optimized
        for day in package["days"]
        for place in day["places"]
    }
    missing = sorted(used_ids.difference(coordinates))
    if missing:
        raise ValueError(f"TourAPI coordinates missing for content_id values: {missing}")

    before_daily: list[float] = []
    after_daily: list[float] = []
    before_package: list[float] = []
    after_package: list[float] = []
    reordered_days = 0
    reordered_packages = 0

    for package in optimized:
        original_package = deepcopy(package)
        day_options = [
            shortest_day_options(day["places"], coordinates)
            for day in package["days"]
        ]
        selected_options = choose_package_options(day_options)
        package_changed = False

        for day, selected in zip(package["days"], selected_options):
            original_places = day["places"]
            before_daily.append(route_distance(original_places, coordinates))
            reordered = [deepcopy(original_places[index]) for index in selected.order]
            for order, place in enumerate(reordered, start=1):
                place["order"] = order
            if [p["content_id"] for p in reordered] != [
                p["content_id"] for p in original_places
            ]:
                reordered_days += 1
                package_changed = True
            day["places"] = reordered
            after_daily.append(route_distance(reordered, coordinates))

        if package_changed:
            reordered_packages += 1
        before_package.append(package_route_distance(original_package, coordinates))
        after_package.append(package_route_distance(package, coordinates))

    daily_errors = 0
    for package in optimized:
        for day in package["days"]:
            actual = route_distance(day["places"], coordinates)
            minimum = min(
                option.internal_km
                for option in shortest_day_options(day["places"], coordinates)
            )
            if actual - minimum > 1e-6:
                daily_errors += 1

    metrics = {
        "coordinate_reference_count": len(used_ids),
        "days_evaluated": len(before_daily),
        "reordered_day_count": reordered_days,
        "reordered_package_count": reordered_packages,
        "daily_route_order_errors": daily_errors,
        "daily_total_before_km": round(sum(before_daily), 2),
        "daily_total_after_km": round(sum(after_daily), 2),
        "daily_distance_saved_km": round(sum(before_daily) - sum(after_daily), 2),
        "daily_distance_saved_percent": round(
            (sum(before_daily) - sum(after_daily)) / sum(before_daily) * 100, 2
        ),
        "average_daily_distance_before_km": round(
            sum(before_daily) / len(before_daily), 2
        ),
        "average_daily_distance_after_km": round(
            sum(after_daily) / len(after_daily), 2
        ),
        "maximum_daily_distance_before_km": round(max(before_daily), 2),
        "maximum_daily_distance_after_km": round(max(after_daily), 2),
        "package_route_total_before_km": round(sum(before_package), 2),
        "package_route_total_after_km": round(sum(after_package), 2),
        "package_route_saved_km": round(sum(before_package) - sum(after_package), 2),
    }
    return optimized, metrics


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
    parser.add_argument(
        "--sample",
        type=Path,
        default=Path("data/package_evaluation/generated_packages.sample.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    package_payload = json.loads(args.packages.read_text(encoding="utf-8"))
    coordinates = load_coordinates(args.raw_tourapi)
    packages, metrics = optimize_packages(package_payload["packages"], coordinates)
    package_payload["packages"] = packages
    write_json(args.packages, package_payload)

    sample_payload = deepcopy(package_payload)
    sample_payload["packages"] = packages[:10]
    write_json(args.sample, sample_payload)

    report = json.loads(args.report.read_text(encoding="utf-8"))
    report["generated_at"] = date.today().isoformat()
    report["source_database"] = "tour_recommender"
    report["route_order_optimization"] = {
        "method": "각 일자의 3~4개 장소 모든 순열 중 최단 동선을 선택하고, 정방향·역방향은 전후 일자와 제주공항 기준으로 결정",
        **metrics,
    }
    report.setdefault("validation", {})["daily_route_order_errors"] = metrics[
        "daily_route_order_errors"
    ]
    report["validation"]["average_daily_straight_distance_km"] = metrics[
        "average_daily_distance_after_km"
    ]
    report["validation"]["maximum_daily_straight_distance_km"] = metrics[
        "maximum_daily_distance_after_km"
    ]
    write_json(args.report, report)

    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
