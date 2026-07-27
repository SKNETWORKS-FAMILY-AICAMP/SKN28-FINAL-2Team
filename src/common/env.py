from __future__ import annotations

import os
from pathlib import Path


def load_env_file(path: str | os.PathLike[str]) -> int:
    """Load missing environment variables from a simple dotenv file."""
    env_path = Path(path)
    if not env_path.exists():
        return 0

    loaded = 0
    with env_path.open(encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line.removeprefix("export ").strip()
            name, value = line.split("=", 1)
            name = name.strip()
            value = _clean_env_value(value.strip())
            if name and name not in os.environ:
                os.environ[name] = value
                loaded += 1
    return loaded


def _clean_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
