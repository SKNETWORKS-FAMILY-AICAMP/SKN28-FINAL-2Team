from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping, Protocol

from src.aihub.similarity import (
    AIHubPatternConfig,
    AIHubPatternService,
    AIHubSimilarityRepository,
)
from src.common.env import load_env_file

from .models import TravelConditions


class RoutePatternProvider(Protocol):
    def build_llm_context(
        self,
        condition: Mapping[str, Any],
    ) -> dict[str, Any]: ...


class AIHubRouteAdapter:
    """Convert prompt-extracted conditions to the AIHub route contract."""

    def __init__(self, service: RoutePatternProvider) -> None:
        self.service = service

    def build_route_context(
        self,
        conditions: TravelConditions,
    ) -> dict[str, Any]:
        return self.service.build_llm_context(conditions.to_aihub_dict())


def create_aihub_route_adapter(
    *,
    env_file: str | Path | None = None,
    top_k: int = 3,
    min_usable_visits: int = 3,
) -> AIHubRouteAdapter:
    if env_file is not None and Path(env_file).exists():
        load_env_file(env_file)
    required = ("MYSQL_USER", "MYSQL_PASSWORD")
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise ValueError(
            "missing MySQL environment variables: " + ", ".join(missing)
        )
    database = os.environ.get("MYSQL_DATABASE", "tour_recommender")
    config = {
        "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.environ.get("MYSQL_PORT", "3306")),
        "user": os.environ["MYSQL_USER"],
        "password": os.environ["MYSQL_PASSWORD"],
        "database": database,
        "connection_timeout": int(os.environ.get("MYSQL_CONNECT_TIMEOUT", "10")),
    }
    repository = AIHubSimilarityRepository(config)
    service = AIHubPatternService(
        repository,
        AIHubPatternConfig(
            top_k=top_k,
            min_usable_visits=min_usable_visits,
        ),
    )
    return AIHubRouteAdapter(service)
