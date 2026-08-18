from __future__ import annotations

import requests

from django.conf import settings


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
    }


def _request_travel_time(
    origin_stop: dict,
    destination_stop: dict,
) -> int:
    """
    출발지 → 목적지 자동차 이동시간을 초 단위로 반환한다.
    """

    params = {
        "origin": (
            f'{origin_stop["longitude"]},'
            f'{origin_stop["latitude"]}'
        ),
        "destination": (
            f'{destination_stop["longitude"]},'
            f'{destination_stop["latitude"]}'
        ),
        "priority": "TIME",
    }

    response = requests.get(
        KAKAO_DIRECTIONS_URL,
        headers=_build_headers(),
        params=params,
        timeout=10,
    )

    if response.status_code != 200:
        raise RuntimeError(
            "카카오 자동차 길찾기 API 호출 실패: "
            f"{response.status_code} "
            f"{response.text}"
        )

    data = response.json()

    routes = data.get("routes", [])

    if not routes:
        raise RuntimeError(
            "카카오 자동차 길찾기 결과가 없습니다."
        )

    route = routes[0]

    result_code = route.get("result_code")

    if result_code != 0:
        raise RuntimeError(
            "카카오 자동차 길찾기 실패: "
            f"result_code={result_code}, "
            f"message={route.get('result_msg')}"
        )

    summary = route.get("summary") or {}

    duration = summary.get("duration")

    if duration is None:
        raise RuntimeError(
            "카카오 길찾기 결과에 이동시간이 없습니다."
        )

    return int(duration)


def build_kakao_time_matrix(
    stops: list[dict],
) -> list[list[int]]:
    """
    각 장소 사이 실제 자동차 이동시간 matrix 생성.

    matrix[from][to] = 이동시간(초)
    """

    stop_count = len(stops)

    if stop_count == 0:
        return []

    for stop in stops:
        if (
            stop.get("latitude") is None
            or stop.get("longitude") is None
        ):
            raise ValueError(
                "카카오 이동시간 계산에 필요한 좌표가 없습니다."
            )

    matrix = [
        [0 for _ in range(stop_count)]
        for _ in range(stop_count)
    ]

    for from_index, from_stop in enumerate(stops):
        for to_index, to_stop in enumerate(stops):

            if from_index == to_index:
                matrix[from_index][to_index] = 0
                continue

            duration = _request_travel_time(
                from_stop,
                to_stop,
            )

            matrix[from_index][to_index] = duration

            print(
                "[Kakao]",
                from_stop.get("title"),
                "→",
                to_stop.get("title"),
                ":",
                duration,
                "초",
            )

    print("=" * 80)
    print("[Kakao] 자동차 이동시간 Matrix")

    for row in matrix:
        print(row)

    print("=" * 80)

    return matrix

def get_kakao_route_path(
    origin_stop: dict,
    destination_stop: dict,
) -> list[dict]:
    """
    출발지 → 목적지 실제 자동차 도로 경로 좌표를 반환한다.

    반환 예:
    [
        {
            "latitude": 33.123,
            "longitude": 126.456,
        },
        ...
    ]
    """

    params = {
        "origin": (
            f'{origin_stop["longitude"]},'
            f'{origin_stop["latitude"]}'
        ),
        "destination": (
            f'{destination_stop["longitude"]},'
            f'{destination_stop["latitude"]}'
        ),
        "priority": "TIME",
        "summary": "false",
        "road_details": "true",
    }

    response = requests.get(
        KAKAO_DIRECTIONS_URL,
        headers=_build_headers(),
        params=params,
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
                longitude = vertexes[index]

                if index + 1 >= len(vertexes):
                    break

                latitude = vertexes[index + 1]

                path.append(
                    {
                        "latitude": latitude,
                        "longitude": longitude,
                    }
                )

    return path