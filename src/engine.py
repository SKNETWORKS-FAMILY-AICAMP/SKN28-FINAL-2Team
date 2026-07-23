from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config.settings import (
    load_chroma_config,
    load_mysql_config,
)

from src.storage.mysql_repository import MySQLPlaceRepository
from src.rag.vector_store import ChromaPlaceRepository
from src.rag.retriever import HybridPlaceRetriever

from src.aihub.similarity import (
    AIHubPatternConfig,
    AIHubPatternService,
    AIHubSimilarityRepository,
)

from src.rag.retrieval import (
    RetrievalConfig,
    RetrievalService,
)


@dataclass(frozen=True)
class AppContainer:
    retrieval_service: RetrievalService
    pattern_service: AIHubPatternService


def create_container(
    project_root: str | Path,
) -> AppContainer:
    mysql_config = load_mysql_config()

    chroma_config = load_chroma_config(
        project_root=project_root,
    )

    mysql_repository = MySQLPlaceRepository(
        mysql_config,
    )

    chroma_repository = ChromaPlaceRepository(
        chroma_config,
    )

    retriever = HybridPlaceRetriever(
        mysql_repository=mysql_repository,
        chroma_repository=chroma_repository,
    )

    retrieval_config = RetrievalConfig(
        project_root=Path(project_root),

        rag_enabled=True,
        aihub_rag_enabled=True,
        custom_rag_enabled=True,

        rag_top_k=5,
        aihub_top_k=3,
        custom_top_k=3,

        aihub_collection="aihub",
        custom_collection="custom",

        rag_bm25_weight=0.5,
        rag_cosine_weight=0.5,
        rag_candidate_k=30,
    )

    retrieval_service = RetrievalService(
        retriever=retriever,
        aihub_repo=chroma_repository,
        custom_repo=chroma_repository,
        config=retrieval_config,
    )

    pattern_repository = AIHubSimilarityRepository(
        mysql_config,
    )

    pattern_service = AIHubPatternService(
        repository=pattern_repository,
        config=AIHubPatternConfig(),
    )

    return AppContainer(
        retrieval_service=retrieval_service,
        pattern_service=pattern_service,
    )