from __future__ import annotations

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from .kakao_route_service import build_kakao_time_matrix


def optimize_stops(stops: list[dict]) -> list[dict]:
    """카카오 자동차 이동시간을 비용으로 사용해 하루 방문 순서를 최적화한다."""
    if len(stops) <= 1:
        return stops
    if any(
        stop.get("latitude") is None or stop.get("longitude") is None
        for stop in stops
    ):
        return stops

    time_matrix = build_kakao_time_matrix(stops)
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

    results = [solve(start) for start in start_candidates]
    valid_results = [result for result in results if result is not None]
    if not valid_results:
        return stops

    best_order, _ = min(valid_results, key=lambda result: result[1])
    optimized = [stops[index] for index in best_order]
    for sequence, stop in enumerate(optimized, start=1):
        stop["sequence"] = sequence
    return optimized
