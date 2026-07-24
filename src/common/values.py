from __future__ import annotations

from typing import Any


def optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
