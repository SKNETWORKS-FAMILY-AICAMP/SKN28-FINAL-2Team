from __future__ import annotations

from pathlib import Path

from src.config.settings import ChromaConfig


TOURAPI_CHROMA_COLLECTION = "jeju_places"


def chroma_config_from_env(
    env_file: str | Path | None = None,
    *,
    project_root: str | Path | None = None,
) -> ChromaConfig:
    """Load shared Chroma settings with the TourAPI collection default."""

    return ChromaConfig.from_env(
        env_file,
        project_root=project_root,
        default_collection=TOURAPI_CHROMA_COLLECTION,
    )
