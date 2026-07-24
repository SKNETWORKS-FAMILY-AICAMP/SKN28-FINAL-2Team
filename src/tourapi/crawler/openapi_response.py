from __future__ import annotations

from typing import Any


def response_body(payload: dict[str, Any]) -> dict[str, Any]:
    response = payload.get("response")
    if not isinstance(response, dict):
        return {}
    body = response.get("body")
    return body if isinstance(body, dict) else {}


def response_items(body: dict[str, Any]) -> list[dict[str, Any]]:
    items = body.get("items")
    if not isinstance(items, dict):
        return []
    item = items.get("item")
    if isinstance(item, list):
        return [value for value in item if isinstance(value, dict)]
    if isinstance(item, dict):
        return [item]
    return []


def as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def validate_positive(name: str, value: int | float) -> None:
    if value < 1:
        raise ValueError(f"{name} must be at least 1.")
