from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

from ..common.env import load_env_file
from ..common.paths import REPOSITORY_ROOT
from ..config.settings import ChromaConfig, MySQLConfig
from ..embeddings.embedder import DEFAULT_EMBEDDING_MODEL, OpenAIEmbeddingClient
from ..storage.chroma import create_chroma_client, get_collection_if_exists
from ..storage.mysql_repository import MySQLPlaceRepository
from .models import PlaceSearchFilters, PlaceSearchResponse, RetrievedPlace
from .service import DEFAULT_TOP_K, PlaceSearchService, PlaceSearchServiceError

_default_service: PlaceSearchService | None = None


def create_place_search_service(
    project_root: str | Path = REPOSITORY_ROOT,
) -> PlaceSearchService:
    """Build a new :class:`PlaceSearchService`.

    Reads ``<project_root>/.env`` without overwriting variables that are
    already set in the process environment. Required settings: ``MYSQL_*``,
    ``OPENAI_API_KEY``, ``OPENAI_EMBEDDING_MODEL`` (optional), ``CHROMA_*``.
    """

    project_root = Path(project_root)
    load_env_file(project_root / ".env")

    mysql_config = MySQLConfig.from_env()
    chroma_config = ChromaConfig.from_env(project_root=project_root)

    repository = MySQLPlaceRepository(mysql_config)
    chroma_client = create_chroma_client(chroma_config)
    collection = get_collection_if_exists(chroma_client, chroma_config.collection_name)
    if collection is None:
        raise PlaceSearchServiceError(
            "Chroma collection "
            f"'{chroma_config.collection_name}' does not exist; "
            "run the indexing pipeline (src/embeddings) first."
        )

    embedder = OpenAIEmbeddingClient(
        api_key=chroma_config.openai_api_key,
        model=os.environ.get("OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
    )
    return PlaceSearchService(repository=repository, collection=collection, embedder=embedder)


def get_place_search_service(
    project_root: str | Path = REPOSITORY_ROOT,
) -> PlaceSearchService:
    """Return a process-wide :class:`PlaceSearchService`, creating it once."""

    global _default_service
    if _default_service is None:
        _default_service = create_place_search_service(project_root)
    return _default_service


def search_places(
    query: str,
    *,
    filters: PlaceSearchFilters | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> PlaceSearchResponse:
    return get_place_search_service().search_places(query, filters=filters, top_k=top_k)


def build_rag_context(
    query: str,
    *,
    filters: PlaceSearchFilters | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> str:
    return get_place_search_service().build_rag_context(query, filters=filters, top_k=top_k)


def get_places_by_ids(content_ids: Sequence[int]) -> list[RetrievedPlace]:
    return get_place_search_service().get_places_by_ids(content_ids)
