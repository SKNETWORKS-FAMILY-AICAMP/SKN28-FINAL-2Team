from __future__ import annotations

import requests
from django.conf import settings


KAKAO_DIRECTIONS_URL = "https://apis-navi.kakaomobility.com/v1/directions"


def _headers() -> dict[str, str]:
    api_key = settings.KAKAO_REST_API_KEY
    if not api_key:
        raise RuntimeError("KAKAO_REST_API_KEY가 설정되어 있지 않습니다.")
    return {"Authorization": f"KakaoAK {api_key}"}


def _directions(origin: dict, destination: dict, *, summary: bool) -> dict:
    response = requests.get(
        KAKAO_DIRECTIONS_URL,
        headers=_headers(),
        params={
            "origin": f'{origin["longitude"]},{origin["latitude"]}',
            "destination": f'{destination["longitude"]},{destination["latitude"]}',
            "priority": "TIME",
            "summary": str(summary).lower(),
            "road_details": "true",
        },
        timeout=10,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"카카오 자동차 길찾기 API 호출 실패: {response.status_code}"
        )

    routes = response.json().get("routes") or []
    if not routes:
        raise RuntimeError("카카오 자동차 길찾기 결과가 없습니다.")

    route = routes[0]
    if route.get("result_code") != 0:
        raise RuntimeError(
            "카카오 자동차 길찾기 실패: "
            f"{route.get('result_msg') or route.get('result_code')}"
        )
    return route


def _request_travel_time(origin: dict, destination: dict) -> int:
    duration = (_directions(origin, destination, summary=True).get("summary") or {}).get(
        "duration"
    )
    if duration is None:
        raise RuntimeError("카카오 길찾기 결과에 이동시간이 없습니다.")
    return int(duration)


def build_kakao_time_matrix(stops: list[dict]) -> list[list[int]]:
    for stop in stops:
        if stop.get("latitude") is None or stop.get("longitude") is None:
            raise ValueError("카카오 이동시간 계산에 필요한 좌표가 없습니다.")

    size = len(stops)
    matrix = [[0 for _ in range(size)] for _ in range(size)]
    for from_index, origin in enumerate(stops):
        for to_index, destination in enumerate(stops):
            if from_index != to_index:
                matrix[from_index][to_index] = _request_travel_time(
                    origin, destination
                )
    return matrix


def get_kakao_route_path(origin: dict, destination: dict) -> list[dict]:
    route = _directions(origin, destination, summary=False)
    path = []
    for section in route.get("sections", []):
        for road in section.get("roads", []):
            vertices = road.get("vertexes", [])
            for index in range(0, len(vertices) - 1, 2):
                path.append(
                    {
                        "longitude": vertices[index],
                        "latitude": vertices[index + 1],
                    }
                )
    return path
