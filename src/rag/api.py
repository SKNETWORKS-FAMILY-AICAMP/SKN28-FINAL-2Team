from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
from typing import Sequence

from src.config.settings import ChromaConfig, MySQLConfig
from src.embeddings.embedder import (
    DEFAULT_EMBEDDING_MODEL,
    OpenAIEmbeddingClient,
)
from src.storage.mysql_repository import MySQLPlaceRepository
from src.storage.tourapi import chroma_config_from_env

from .models import PlaceSearchFilters, PlaceSearchResponse
from .service import PlaceSearchService
from .vector_store import ChromaPlaceRepository


def create_place_search_service(
    *,
    project_root: str | Path | None = None,
    env_file: str | Path | None = None,
) -> PlaceSearchService:
    """Create the shared MySQL + Chroma retrieval service.

    If ``env_file`` is omitted, ``<project_root>/.env`` is loaded when present.
    Existing process environment variables always take precedence.
    """

    root = Path(project_root or Path.cwd()).resolve()
    resolved_env = _resolve_env_file(root, env_file)
    mysql_config = MySQLConfig.from_env(resolved_env)
    chroma_config = chroma_config_from_env(
        resolved_env,
        project_root=root,
    )
    embedder = OpenAIEmbeddingClient(
        api_key=chroma_config.openai_api_key,
        model=os.environ.get(
            "OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL
        ),
    )
    return PlaceSearchService(
        mysql_repository=MySQLPlaceRepository(mysql_config),
        vector_repository=ChromaPlaceRepository(
            chroma_config,
            embedder=embedder,
        ),
    )


def get_place_search_service(
    *,
    project_root: str | Path | None = None,
    env_file: str | Path | None = None,
) -> PlaceSearchService:
    root = str(Path(project_root or Path.cwd()).resolve())
    resolved_env = _resolve_env_file(Path(root), env_file)
    return _cached_service(root, str(resolved_env) if resolved_env else "")


def search_places(
    query: str,
    *,
    filters: PlaceSearchFilters | None = None,
    top_k: int = 10,
    include_aihub_evidence: bool = True,
    project_root: str | Path | None = None,
    env_file: str | Path | None = None,
) -> PlaceSearchResponse:
    """Convenience function for itinerary RAG callers."""

    return get_place_search_service(
        project_root=project_root,
        env_file=env_file,
    ).search_places(
        query,
        filters=filters,
        top_k=top_k,
        include_aihub_evidence=include_aihub_evidence,
    )


def build_rag_context(
    query: str,
    *,
    filters: PlaceSearchFilters | None = None,
    top_k: int = 10,
    include_aihub_evidence: bool = True,
    project_root: str | Path | None = None,
    env_file: str | Path | None = None,
) -> str:
    """Return compact JSON facts ready to include in an LLM prompt."""

    response = search_places(
        query,
        filters=filters,
        top_k=top_k,
        include_aihub_evidence=include_aihub_evidence,
        project_root=project_root,
        env_file=env_file,
    )
    return response.to_context_json()


def get_places_by_ids(
    content_ids: Sequence[int],
    *,
    project_root: str | Path | None = None,
    env_file: str | Path | None = None,
) -> list[dict]:
    return get_place_search_service(
        project_root=project_root,
        env_file=env_file,
    ).get_places_by_ids(content_ids)


@lru_cache(maxsize=4)
def _cached_service(root: str, env_file: str) -> PlaceSearchService:
    return create_place_search_service(
        project_root=root,
        env_file=env_file or None,
    )


def _resolve_env_file(
    project_root: Path,
    env_file: str | Path | None,
) -> Path | None:
    if env_file is not None:
        return Path(env_file).resolve()
    default_env = project_root / ".env"
    return default_env if default_env.exists() else None
