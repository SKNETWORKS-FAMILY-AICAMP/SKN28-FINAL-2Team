from __future__ import annotations

import requests

from django.conf import settings


KAKAO_WAYPOINTS_DIRECTIONS_URL = (
    "https://apis-navi.kakaomobility.com/v1/waypoints/directions"
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


def get_kakao_day_route_path(
    stops: list[dict],
) -> list[dict]:
    """
    하루 일정에 저장된 방문 순서를 그대로 유지하면서
    실제 자동차 도로 경로 좌표를 조회한다.

    예:
    A → B → C → D → E

    origin      = A
    waypoints   = B, C, D
    destination = E

    하루당 Kakao API 1회만 호출한다.
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

    # 경유지 최대 30개
    # 출발지 + 목적지를 포함하면 하루 최대 32개 장소
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

    if route.get("result_code") != 0:
        raise RuntimeError(
            "카카오 실제 경로 조회 실패: "
            f"result_code={route.get('result_code')}, "
            f"message={route.get('result_msg')}"
        )

    path = []

    for section in route.get("sections", []):
        for road in section.get("roads", []):
            vertexes = road.get("vertexes", [])

            # vertexes:
            # [longitude, latitude, longitude, latitude, ...]
            for index in range(0, len(vertexes), 2):

                if index + 1 >= len(vertexes):
                    break

                longitude = vertexes[index]
                latitude = vertexes[index + 1]

                point = {
                    "latitude": latitude,
                    "longitude": longitude,
                }

                # 같은 좌표가 연속으로 들어오는 경우만 제거
                if path and path[-1] == point:
                    continue

                path.append(point)

    return path