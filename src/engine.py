from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.rag import PlaceSearchService, create_place_search_service


@dataclass(frozen=True)
class AppContainer:
    retrieval_service: PlaceSearchService
    pattern_service: None = None


def create_container(
    project_root: str | Path,
) -> AppContainer:
    retrieval_service = create_place_search_service(
        project_root=project_root,
    )
    return AppContainer(
        retrieval_service=retrieval_service,
    )
