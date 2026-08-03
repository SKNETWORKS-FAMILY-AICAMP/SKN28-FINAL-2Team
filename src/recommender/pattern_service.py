from __future__ import annotations

from pathlib import Path

from ..aihub.similarity import AIHubPatternConfig, AIHubPatternService, AIHubSimilarityRepository
from ..common.env import load_env_file
from ..common.paths import REPOSITORY_ROOT
from ..config.settings import MySQLConfig


def create_pattern_service(
    project_root: str | Path = REPOSITORY_ROOT,
    *,
    config: AIHubPatternConfig | None = None,
) -> AIHubPatternService:
    project_root = Path(project_root)
    load_env_file(project_root / ".env")

    mysql_config = MySQLConfig.from_env()
    repository = AIHubSimilarityRepository(mysql_config)
    return AIHubPatternService(repository, config)
