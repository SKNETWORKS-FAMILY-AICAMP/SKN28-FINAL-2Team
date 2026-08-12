from __future__ import annotations

import math

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from .kakao_route_service import build_kakao_time_matrix

# 카카오 자동차 길찾기는 출발지/도착지가 이 거리(미터) 이내면
# "출발지와 도착지가 5m 이내" 같은 오류로 실패한다. 그런 좌표 쌍이 있으면
# 애초에 카카오 API를 호출하지 않고 최적화를 건너뛴다.
_MIN_ROUTABLE_DISTANCE_M = 5.0


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_m = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius_m * math.asin(min(1.0, math.sqrt(a)))


def _has_too_close_pair(stops: list[dict]) -> bool:
    for i in range(len(stops)):
        for j in range(i + 1, len(stops)):
            lat1, lon1 = stops[i].get("latitude"), stops[i].get("longitude")
            lat2, lon2 = stops[j].get("latitude"), stops[j].get("longitude")
            if None in (lat1, lon1, lat2, lon2):
                continue
            if _haversine_m(lat1, lon1, lat2, lon2) < _MIN_ROUTABLE_DISTANCE_M:
                return True
    return False


def optimize_stops(stops: list[dict]) -> list[dict]:
    """카카오 자동차 이동시간을 비용으로 사용해 하루 방문 순서를 최적화한다.

    카카오 길찾기 API가 실패할 수 있는 상황(좌표 5m 이내, API 오류, 네트워크
    오류 등)에서는 예외를 던지지 않고 원래 순서를 그대로 반환한다. 순서
    최적화는 "있으면 좋은" 부가 기능이므로, 이 함수의 실패가 상위 호출부의
    일정 저장 자체를 막아서는 안 된다.
    """
    if len(stops) <= 1:
        return stops
    if any(
        stop.get("latitude") is None or stop.get("longitude") is None
        for stop in stops
    ):
        return stops
    if _has_too_close_pair(stops):
        # 서로 5m 이내로 붙어있는 장소가 있으면 카카오 API가 실패하므로
        # 아예 호출하지 않고 기존 순서를 유지한다.
        return stops

    try:
        time_matrix = build_kakao_time_matrix(stops)
    except Exception:
        # 카카오 API 호출/응답 문제 - 최적화만 건너뛴다.
        return stops

    stop_count = len(stops)
    start_candidates = [
        index for index, stop in enumerate(stops) if stop.get("role") != "food"
    ] or list(range(stop_count))

    def solve(start_index: int):
        dummy_node = stop_count
        manager = pywrapcp.RoutingIndexManager(
            stop_count + 1, 1, [start_index], [dummy_node]
        )
        routing = pywrapcp.RoutingModel(manager)

        def travel_time(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            if from_node == dummy_node or to_node == dummy_node:
                return 0
            return time_matrix[from_node][to_node]

        callback_index = routing.RegisterTransitCallback(travel_time)
        routing.SetArcCostEvaluatorOfAllVehicles(callback_index)
        parameters = pywrapcp.DefaultRoutingSearchParameters()
        parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        solution = routing.SolveWithParameters(parameters)
        if solution is None:
            return None

        order = []
        index = routing.Start(0)
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node != dummy_node:
                order.append(node)
            index = solution.Value(routing.NextVar(index))
        total = sum(
            time_matrix[order[i]][order[i + 1]] for i in range(len(order) - 1)
        )
        return order, total

    try:
        results = [solve(start) for start in start_candidates]
        valid_results = [result for result in results if result is not None]
        if not valid_results:
            return stops

        best_order, _ = min(valid_results, key=lambda result: result[1])
        optimized = [stops[index] for index in best_order]
        for sequence, stop in enumerate(optimized, start=1):
            stop["sequence"] = sequence
        return optimized
    except Exception:
        # OR-Tools 계산 실패 등 - 최적화만 건너뛰고 원본 순서를 유지한다.
        return stops
