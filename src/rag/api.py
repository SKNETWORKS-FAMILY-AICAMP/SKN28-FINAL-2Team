from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Sequence

from src.common.env import load_env_file
from src.config.settings import MySQLConfig
from src.embeddings.embedder import (
    DEFAULT_EMBEDDING_MODEL,
    OpenAIEmbeddingClient,
)
from src.storage.chroma import create_chroma_client, get_collection_if_exists
from src.storage.mysql_repository import MySQLPlaceRepository
from src.storage.tourapi import chroma_config_from_env

from .models import PlaceSearchFilters, PlaceSearchResponse
from .service import PlaceSearchService


def create_place_search_service(
    *,
    project_root: str | Path | None = None,
    env_file: str | Path | None = None,
) -> PlaceSearchService:
    root = Path(project_root or Path.cwd())
    resolved_env = Path(env_file) if env_file else root / ".env"
    if resolved_env.exists():
        load_env_file(resolved_env)
    mysql = MySQLPlaceRepository(MySQLConfig.from_env())
    chroma_config = chroma_config_from_env(project_root=root)
    client = create_chroma_client(chroma_config)
    collection = get_collection_if_exists(
        client,
        chroma_config.collection_name,
    )
    if collection is None:
        raise RuntimeError(
            f"Chroma collection does not exist: {chroma_config.collection_name}"
        )
    embedder = OpenAIEmbeddingClient(
        api_key=chroma_config.openai_api_key,
        model=os.environ.get(
            "OPENAI_EMBEDDING_MODEL",
            DEFAULT_EMBEDDING_MODEL,
        ),
    )
    return PlaceSearchService(
        mysql_repository=mysql,
        chroma_collection=collection,
        embedder=embedder,
    )


@lru_cache(maxsize=1)
def get_place_search_service() -> PlaceSearchService:
    return create_place_search_service(project_root=Path.cwd())


def search_places(
    query: str,
    *,
    filters: PlaceSearchFilters | None = None,
    top_k: int = 10,
    include_aihub_evidence: bool = False,
) -> PlaceSearchResponse:
    return get_place_search_service().search_places(
        query,
        filters=filters,
        top_k=top_k,
        include_aihub_evidence=include_aihub_evidence,
    )


def get_places_by_ids(content_ids: Sequence[int]) -> list[dict]:
    return get_place_search_service().get_places_by_ids(content_ids)


def build_rag_context(
    query: str,
    *,
    filters: PlaceSearchFilters | None = None,
    top_k: int = 10,
) -> str:
    response = search_places(query, filters=filters, top_k=top_k)
    return json.dumps(response.to_dict(), ensure_ascii=False)
