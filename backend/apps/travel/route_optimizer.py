from __future__ import annotations

import math

from ortools.constraint_solver import pywrapcp
from ortools.constraint_solver import routing_enums_pb2


def build_distance_matrix(stops: list[dict]) -> list[list[int]]:
    """위도/경도를 이용해 장소 간 직선거리 matrix를 미터 단위로 생성한다."""

    stop_count = len(stops)

    if stop_count == 0:
        return []

    earth_radius = 6_371_000

    matrix = [
        [0 for _ in range(stop_count)]
        for _ in range(stop_count)
    ]

    for from_index, from_stop in enumerate(stops):
        lat1 = math.radians(float(from_stop["latitude"]))
        lon1 = math.radians(float(from_stop["longitude"]))

        for to_index, to_stop in enumerate(stops):
            if from_index == to_index:
                continue

            lat2 = math.radians(float(to_stop["latitude"]))
            lon2 = math.radians(float(to_stop["longitude"]))

            delta_lat = lat2 - lat1
            delta_lon = lon2 - lon1

            a = (
                math.sin(delta_lat / 2) ** 2
                + math.cos(lat1)
                * math.cos(lat2)
                * math.sin(delta_lon / 2) ** 2
            )

            distance = (
                2
                * earth_radius
                * math.asin(math.sqrt(a))
            )

            matrix[from_index][to_index] = int(distance)

    return matrix
def optimize_stops(
    stops: list[dict],
) -> list[dict]:
    """
    하루 일정의 stop 목록을 좌표 기반 직선거리 기준으로
    OR-Tools를 이용해 최적화한다.

    - 특정 첫 장소를 고정하지 않는다.
    - food 장소는 시작점 후보에서 제외한다.
    - food가 아닌 각 장소를 시작점으로 OR-Tools를 실행한다.
    - 각 결과의 전체 이동거리를 비교한다.
    - 총 직선거리가 가장 짧은 경로를 최종 선택한다.
    - 종료점은 자유롭다.
    - 시간 정보는 사용하지 않는다.
    """

    if len(stops) <= 1:
        return stops

    # -------------------------------------------------
    # 좌표 확인
    # -------------------------------------------------
    for stop in stops:
        if (
            stop.get("latitude") is None
            or stop.get("longitude") is None
        ):
            print(
                "[OR-Tools] 좌표가 없는 장소가 있어 "
                "기존 순서를 유지합니다."
            )
            return stops

    # -------------------------------------------------
    # 좌표 기반 거리 Matrix
    # Kakao API를 호출하지 않는다.
    # -------------------------------------------------
    time_matrix = build_distance_matrix(stops)

    stop_count = len(stops)

    # -------------------------------------------------
    # 시작점 후보
    #
    # food는 시작점 후보에서 제외
    # -------------------------------------------------
    candidate_start_indices = [
        index
        for index, stop in enumerate(stops)
        if stop.get("role") != "food"
    ]

    # 모든 장소가 food인 특수한 경우에는
    # 전체 장소를 시작점 후보로 사용
    if not candidate_start_indices:
        candidate_start_indices = list(
            range(stop_count)
        )

    print("=" * 80)
    print("[OR-Tools] 시작점 후보")

    for start_index in candidate_start_indices:
        print(
            start_index,
            stops[start_index].get("role"),
            stops[start_index].get("title"),
        )

    print("=" * 80)

    # -------------------------------------------------
    # 특정 시작점으로 경로 하나 계산
    # -------------------------------------------------
    def solve_route(
        start_index: int,
    ) -> tuple[list[int], int] | None:

        # 종료점을 자유롭게 만들기 위한 가상 노드
        dummy_node = stop_count
        total_nodes = stop_count + 1

        manager = pywrapcp.RoutingIndexManager(
            total_nodes,
            1,
            [start_index],
            [dummy_node],
        )

        routing = pywrapcp.RoutingModel(
            manager
        )

        # ---------------------------------------------
        # 이동거리 비용
        # ---------------------------------------------
        def time_callback(
            from_index,
            to_index,
        ):
            from_node = manager.IndexToNode(
                from_index
            )

            to_node = manager.IndexToNode(
                to_index
            )

            # 마지막 실제 장소 → 가상 종료점
            # 비용은 0
            if to_node == dummy_node:
                return 0

            if from_node == dummy_node:
                return 0

            return time_matrix[
                from_node
            ][to_node]

        time_callback_index = (
            routing.RegisterTransitCallback(
                time_callback
            )
        )

        routing.SetArcCostEvaluatorOfAllVehicles(
            time_callback_index
        )

        # ---------------------------------------------
        # 탐색 설정
        # ---------------------------------------------
        search_parameters = (
            pywrapcp
            .DefaultRoutingSearchParameters()
        )

        search_parameters.first_solution_strategy = (
            routing_enums_pb2
            .FirstSolutionStrategy
            .PATH_CHEAPEST_ARC
        )

        solution = routing.SolveWithParameters(
            search_parameters
        )

        if solution is None:
            return None

        # ---------------------------------------------
        # 경로 추출
        # ---------------------------------------------
        ordered_indices = []

        index = routing.Start(0)

        while not routing.IsEnd(index):
            node = manager.IndexToNode(
                index
            )

            if node != dummy_node:
                ordered_indices.append(
                    node
                )

            index = solution.Value(
                routing.NextVar(index)
            )

        # ---------------------------------------------
        # 전체 전체 이동시간 계산
        # ---------------------------------------------
        total_travel_time = 0

        for route_index in range(
            len(ordered_indices) - 1
        ):
            from_node = (
                ordered_indices[
                    route_index
                ]
            )

            to_node = (
                ordered_indices[
                    route_index + 1
                ]
            )

            total_travel_time += (
                time_matrix[
                    from_node
                ][to_node]
            )

        return (
            ordered_indices,
            total_travel_time,
        )

    # -------------------------------------------------
    # 가능한 시작점을 전부 시험
    # -------------------------------------------------
    best_order = None
    best_total_time = None
    best_start_index = None

    for start_index in candidate_start_indices:

        result = solve_route(
            start_index
        )

        if result is None:
            print(
                "[OR-Tools] 시작점 경로 계산 실패:",
                stops[start_index].get(
                    "title"
                ),
            )
            continue

        ordered_indices, total_time = result

        print(
            "[OR-Tools] 시작점:",
            stops[start_index].get(
                "title"
            ),
            "| 총 이동거리:",
            total_time,
            "m",
        )

        print(
            "  경로:",
            " → ".join(
                stops[index].get(
                    "title",
                    ""
                )
                for index
                in ordered_indices
            ),
        )

        if (
            best_total_time is None
            or total_time
            < best_total_time
        ):
            best_total_time = (
                total_time
            )

            best_order = (
                ordered_indices
            )

            best_start_index = (
                start_index
            )

    # -------------------------------------------------
    # 모든 계산이 실패한 경우
    # -------------------------------------------------
    if best_order is None:
        print(
            "[OR-Tools] 모든 경로 계산 실패 - "
            "기존 순서를 유지합니다."
        )
        return stops

    # -------------------------------------------------
    # 최종 최적 경로 생성
    # -------------------------------------------------
    optimized = [
        stops[index]
        for index in best_order
    ]

    # 방문 순서 재부여
    for sequence, stop in enumerate(
        optimized,
        start=1,
    ):
        stop["sequence"] = sequence

    # -------------------------------------------------
    # 최종 로그
    # -------------------------------------------------
    print("=" * 80)
    print("[OR-Tools] 최종 경로 선택")

    print(
        "선택된 시작점:",
        stops[
            best_start_index
        ].get("title"),
    )

    print(
        "총 직선 이동거리:",
        best_total_time,
        "m",
    )

    print("-" * 80)

    for stop in optimized:
        print(
            stop["sequence"],
            stop.get("role"),
            stop.get("title"),
            stop.get("latitude"),
            stop.get("longitude"),
        )

    print("=" * 80)

    return optimized