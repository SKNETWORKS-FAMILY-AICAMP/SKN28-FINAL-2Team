from __future__ import annotations

import requests

from django.conf import settings


KAKAO_WAYPOINTS_DIRECTIONS_URL = (
    "https://apis-navi.kakaomobility.com/v1/waypoints/directions"
)

KAKAO_DIRECTIONS_URL = (
    "https://apis-navi.kakaomobility.com/v1/directions"
)


def _build_headers() -> dict[str, str]:
    api_key = settings.KAKAO_REST_API_KEY

    if not api_key:
        raise RuntimeError(
            "KAKAO_REST_API_KEY가 설정되어 있지 않습니다."
        )

    return {
        "Authorization": f"KakaoAK {api_key}",
        "Content-Type": "application/json",
    }


def _extract_path_from_route(route: dict) -> list[dict]:
    path = []

    for section in route.get("sections", []):
        for road in section.get("roads", []):
            vertexes = road.get("vertexes", [])

            for index in range(0, len(vertexes), 2):
                if index + 1 >= len(vertexes):
                    break

                longitude = vertexes[index]
                latitude = vertexes[index + 1]

                point = {
                    "latitude": latitude,
                    "longitude": longitude,
                }

                if path and path[-1] == point:
                    continue

                path.append(point)

    return path


def _get_kakao_segment_path(
    origin: dict,
    destination: dict,
) -> list[dict]:
    """
    하루 전체 경로 조회가 실패한 경우에만 사용한다.
    두 장소 사이 실제 자동차 도로 경로를 조회한다.
    """

    params = {
        "origin": (
            f"{float(origin['longitude'])},"
            f"{float(origin['latitude'])}"
        ),
        "destination": (
            f"{float(destination['longitude'])},"
            f"{float(destination['latitude'])}"
        ),
        "priority": "TIME",
        "road_details": "true",
    }

    try:
        response = requests.get(
            KAKAO_DIRECTIONS_URL,
            headers=_build_headers(),
            params=params,
            timeout=10,
        )
    except requests.RequestException:
        return []

    if response.status_code != 200:
        return []

    data = response.json()
    routes = data.get("routes", [])

    if not routes:
        return []

    route = routes[0]

    if route.get("result_code") != 0:
        return []

    return _extract_path_from_route(route)


def _get_segment_fallback_path(
    stops: list[dict],
) -> list[dict]:
    """
    하루 전체 경로 조회가 101/103으로 실패했을 때만 호출한다.

    각 구간별로:
    - 실제 도로 경로 조회 성공 → 실제 도로 좌표 사용
    - 실패 → 해당 구간만 직선 연결
    """

    path = []

    for index in range(len(stops) - 1):
        origin = stops[index]
        destination = stops[index + 1]

        segment_path = _get_kakao_segment_path(
            origin,
            destination,
        )

        if segment_path:
            for point in segment_path:
                if path and path[-1] == point:
                    continue

                path.append(point)

        else:
            fallback_points = [
                {
                    "latitude": float(origin["latitude"]),
                    "longitude": float(origin["longitude"]),
                },
                {
                    "latitude": float(destination["latitude"]),
                    "longitude": float(destination["longitude"]),
                },
            ]

            for point in fallback_points:
                if path and path[-1] == point:
                    continue

                path.append(point)

    return path


def get_kakao_day_route_path(
    stops: list[dict],
) -> list[dict]:
    """
    하루 일정에 저장된 방문 순서를 그대로 유지하면서
    실제 자동차 도로 경로 좌표를 조회한다.

    1차:
    하루 전체 경로를 Kakao API 1회로 조회한다.

    2차:
    경유지/도착지 주변 도로 탐색 실패(101, 103)인 경우에만
    구간별 실제 경로를 조회한다.

    구간 조회까지 실패한 구간만 직선으로 연결한다.
    """

    if len(stops) < 2:
        return []

    for stop in stops:
        if (
            stop.get("latitude") is None
            or stop.get("longitude") is None
        ):
            raise ValueError(
                "카카오 실제 경로 조회에 필요한 좌표가 없습니다."
            )

    if len(stops) > 32:
        raise ValueError(
            "하루 일정 장소가 너무 많습니다. "
            "카카오 다중 경유지는 최대 30개까지 지원합니다."
        )

    origin = stops[0]
    destination = stops[-1]
    waypoints = stops[1:-1]

    payload = {
        "origin": {
            "name": str(origin.get("title") or ""),
            "x": float(origin["longitude"]),
            "y": float(origin["latitude"]),
        },
        "destination": {
            "name": str(destination.get("title") or ""),
            "x": float(destination["longitude"]),
            "y": float(destination["latitude"]),
        },
        "waypoints": [
            {
                "name": str(stop.get("title") or ""),
                "x": float(stop["longitude"]),
                "y": float(stop["latitude"]),
            }
            for stop in waypoints
        ],
        "priority": "TIME",
        "alternatives": False,
        "road_details": True,
        "summary": False,
    }

    response = requests.post(
        KAKAO_WAYPOINTS_DIRECTIONS_URL,
        headers=_build_headers(),
        json=payload,
        timeout=10,
    )

    if response.status_code != 200:
        raise RuntimeError(
            "카카오 실제 경로 조회 실패: "
            f"{response.status_code} "
            f"{response.text}"
        )

    data = response.json()
    routes = data.get("routes", [])

    if not routes:
        return []

    route = routes[0]
    result_code = route.get("result_code")

    # 경유지/도착지 주변 도로 탐색 실패
    # 이 경우에만 구간별 fallback 수행
    if result_code in {101, 103}:
        return _get_segment_fallback_path(stops)

    if result_code != 0:
        raise RuntimeError(
            "카카오 실제 경로 조회 실패: "
            f"result_code={result_code}, "
            f"message={route.get('result_msg')}"
        )

    return _extract_path_from_route(route)
    return _extract_path_from_route(route)
