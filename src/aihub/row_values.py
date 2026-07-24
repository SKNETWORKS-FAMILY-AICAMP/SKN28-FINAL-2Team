from __future__ import annotations

import json
from typing import Any, Mapping


def stringify_row(row: Mapping[str, Any]) -> dict[str, str]:
    return {key: "" if value is None else str(value) for key, value in row.items()}


def json_strings(value: Any) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    payload = value if isinstance(value, list) else json.loads(str(value))
    if not isinstance(payload, list):
        raise ValueError("AIHub aliases and POI IDs must be JSON arrays")
    return tuple(str(item).strip() for item in payload if str(item).strip())


def required_int(value: Any, field_name: str) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer: {value}") from exc


def optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"coordinate must be numeric: {value}") from exc
