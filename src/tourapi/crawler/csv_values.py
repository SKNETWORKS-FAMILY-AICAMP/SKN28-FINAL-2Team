"""CSV serialization helpers shared by collection and export pipelines."""

from __future__ import annotations

import json
from typing import Any


def csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return "" if value is None else value
