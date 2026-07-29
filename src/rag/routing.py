from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
import os
from typing import Any, Callable, Mapping, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .retrieval import haversine_km


Coordinate = tuple[float, float]
JsonRequester = Callable[[Request, float], Mapping[str, Any]]


class RouteProviderError(RuntimeError):
    """Raised when a road-routing provider cannot produce a usable route."""


@dataclass(frozen=True)
class RouteEstimate:
    """Travel metric returned by a routing provider.

    ``verified`` is true only when the provider used an actual road/transit
    network. Straight-line estimates are deliberately marked unverified.
    """

    distance_km: float
    duration_minutes: int
    provider: str
    verified: bool


class RouteMetricsProvider(Protocol):
    def estimate(
        self,
        origin: Coordinate,
        destination: Coordinate,
        *,
        transport: str,
    ) -> RouteEstimate: ...


class HaversineRouteMetricsProvider:
    """Offline fallback used when no road-routing adapter is supplied."""

    _SPEED_KMH = {
        "rental_car": 38.0,
        "own_car": 38.0,
        "taxi": 38.0,
        "public_transit": 24.0,
        "mixed": 30.0,
    }

    def estimate(
        self,
        origin: Coordinate,
        destination: Coordinate,
        *,
        transport: str,
    ) -> RouteEstimate:
        distance = haversine_km(*origin, *destination)
        speed = self._SPEED_KMH.get(transport, 30.0)
        return RouteEstimate(
            distance_km=distance,
            duration_minutes=max(10, round(distance / speed * 60)),
            provider="haversine_estimate",
            verified=False,
        )


class KakaoMobilityRouteProvider:
    """Kakao Mobility car directions adapter.

    Kakao expects coordinates in longitude,latitude order.
    """

    ENDPOINT = "https://apis-navi.kakaomobility.com/v1/directions"

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 8.0,
        requester: JsonRequester | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Kakao REST API key must not be blank")
        self._api_key = api_key.strip()
        self._timeout = timeout
        self._requester = requester or _request_json

    def estimate(
        self,
        origin: Coordinate,
        destination: Coordinate,
        *,
        transport: str,
    ) -> RouteEstimate:
        if transport == "public_transit":
            raise RouteProviderError(
                "Kakao Mobility car directions does not support public transit"
            )
        query = urlencode(
            {
                "origin": f"{origin[1]:.7f},{origin[0]:.7f}",
                "destination": (
                    f"{destination[1]:.7f},{destination[0]:.7f}"
                ),
                "priority": "RECOMMEND",
                "summary": "true",
            }
        )
        request = Request(
            f"{self.ENDPOINT}?{query}",
            headers={
                "Authorization": f"KakaoAK {self._api_key}",
                "Content-Type": "application/json",
            },
            method="GET",
        )
        payload = self._requester(request, self._timeout)
        routes = payload.get("routes")
        if not isinstance(routes, list) or not routes:
            raise RouteProviderError("Kakao returned no routes")
        route = routes[0]
        if not isinstance(route, Mapping):
            raise RouteProviderError("Kakao returned an invalid route")
        result_code = int(route.get("result_code") or 0)
        if result_code != 0:
            raise RouteProviderError(
                f"Kakao route failed with result_code={result_code}"
            )
        summary = route.get("summary")
        if not isinstance(summary, Mapping):
            raise RouteProviderError("Kakao route summary is missing")
        try:
            distance_meters = float(summary["distance"])
            duration_seconds = float(summary["duration"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RouteProviderError(
                "Kakao route summary has invalid distance or duration"
            ) from exc
        return RouteEstimate(
            distance_km=distance_meters / 1000.0,
            duration_minutes=max(1, round(duration_seconds / 60.0)),
            provider="kakao_mobility",
            verified=True,
        )


class GoogleRoutesProvider:
    """Google Routes API v2 adapter used when a Maps API key is configured."""

    ENDPOINT = "https://routes.googleapis.com/directions/v2:computeRoutes"

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 8.0,
        requester: JsonRequester | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Google Maps API key must not be blank")
        self._api_key = api_key.strip()
        self._timeout = timeout
        self._requester = requester or _request_json

    def estimate(
        self,
        origin: Coordinate,
        destination: Coordinate,
        *,
        transport: str,
    ) -> RouteEstimate:
        travel_mode = (
            "TRANSIT" if transport == "public_transit" else "DRIVE"
        )
        body: dict[str, Any] = {
            "origin": {"location": {"latLng": _lat_lng(origin)}},
            "destination": {
                "location": {"latLng": _lat_lng(destination)}
            },
            "travelMode": travel_mode,
            "languageCode": "ko",
            "units": "METRIC",
        }
        if travel_mode == "DRIVE":
            body["routingPreference"] = "TRAFFIC_AWARE"
        request = Request(
            self.ENDPOINT,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self._api_key,
                "X-Goog-FieldMask": "routes.duration,routes.distanceMeters",
            },
            method="POST",
        )
        payload = self._requester(request, self._timeout)
        routes = payload.get("routes")
        if not isinstance(routes, list) or not routes:
            raise RouteProviderError("Google returned no routes")
        route = routes[0]
        if not isinstance(route, Mapping):
            raise RouteProviderError("Google returned an invalid route")
        try:
            distance_meters = float(route["distanceMeters"])
            duration_seconds = _duration_seconds(str(route["duration"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise RouteProviderError(
                "Google route has invalid distance or duration"
            ) from exc
        return RouteEstimate(
            distance_km=distance_meters / 1000.0,
            duration_minutes=max(1, round(duration_seconds / 60.0)),
            provider="google_routes",
            verified=True,
        )


class FallbackRouteMetricsProvider:
    """Try configured road providers, then use an explicit estimate fallback."""

    def __init__(
        self,
        providers: Sequence[RouteMetricsProvider],
        *,
        fallback: RouteMetricsProvider | None = None,
    ) -> None:
        self._providers = tuple(providers)
        self._fallback = fallback or HaversineRouteMetricsProvider()

    def estimate(
        self,
        origin: Coordinate,
        destination: Coordinate,
        *,
        transport: str,
    ) -> RouteEstimate:
        for provider in self._providers:
            try:
                return provider.estimate(
                    origin,
                    destination,
                    transport=transport,
                )
            except RouteProviderError:
                continue
        return self._fallback.estimate(
            origin,
            destination,
            transport=transport,
        )


class CachedRouteMetricsProvider:
    """Small in-process cache for an injected road-routing provider."""

    def __init__(
        self,
        provider: RouteMetricsProvider,
        *,
        maxsize: int = 2048,
    ) -> None:
        self._provider = provider
        self._cached = lru_cache(maxsize=maxsize)(self._estimate)

    def estimate(
        self,
        origin: Coordinate,
        destination: Coordinate,
        *,
        transport: str,
    ) -> RouteEstimate:
        rounded_origin = (round(origin[0], 6), round(origin[1], 6))
        rounded_destination = (
            round(destination[0], 6),
            round(destination[1], 6),
        )
        return self._cached(
            rounded_origin,
            rounded_destination,
            transport,
        )

    def _estimate(
        self,
        origin: Coordinate,
        destination: Coordinate,
        transport: str,
    ) -> RouteEstimate:
        return self._provider.estimate(
            origin,
            destination,
            transport=transport,
        )


def create_route_metrics_provider_from_env(
    env: Mapping[str, str] | None = None,
) -> RouteMetricsProvider:
    values = env or os.environ
    providers: list[RouteMetricsProvider] = []
    kakao_enabled = str(
        values.get("KAKAO_MOBILITY_ENABLED", "")
    ).strip().lower() in {"1", "true", "yes", "on"}
    kakao_key = str(values.get("KAKAO_REST_API_KEY", "")).strip()
    if kakao_enabled and kakao_key:
        providers.append(KakaoMobilityRouteProvider(kakao_key))
    google_key = str(
        values.get("GOOGLE_MAPS_API_KEY")
        or values.get("GOOGLE_ROUTES_API_KEY")
        or ""
    ).strip()
    if google_key:
        providers.append(GoogleRoutesProvider(google_key))
    return CachedRouteMetricsProvider(
        FallbackRouteMetricsProvider(providers)
    )


def _lat_lng(coordinates: Coordinate) -> dict[str, float]:
    return {
        "latitude": coordinates[0],
        "longitude": coordinates[1],
    }


def _duration_seconds(value: str) -> float:
    if not value.endswith("s"):
        raise ValueError("Google duration must end with 's'")
    return float(value[:-1])


def _request_json(
    request: Request,
    timeout: float,
) -> Mapping[str, Any]:
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RouteProviderError(f"route API request failed: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise RouteProviderError("route API response must be an object")
    return payload
