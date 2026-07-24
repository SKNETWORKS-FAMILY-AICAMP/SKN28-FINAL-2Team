from __future__ import annotations

from collections.abc import Mapping, Sequence
import os
from typing import Any

from src.config.settings import ChromaConfig
from src.embeddings.embedder import (
    DEFAULT_EMBEDDING_MODEL,
    OpenAIEmbeddingClient,
)
from src.embeddings.indexer import EmbeddingProvider
from src.storage.chroma import create_chroma_client, get_collection_if_exists

from .models import PlaceSearchFilters, VectorCandidate


class PlaceVectorSearchError(RuntimeError):
    """Raised when the TourAPI Chroma collection cannot be searched."""


class ChromaPlaceRepository:
    def __init__(
        self,
        config: ChromaConfig,
        *,
        embedder: EmbeddingProvider | None = None,
        client: Any | None = None,
    ) -> None:
        self.config = config
        self._client = client or create_chroma_client(config)
        self._embedder = embedder or OpenAIEmbeddingClient(
            api_key=config.openai_api_key,
            model=os.environ.get(
                "OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL
            ),
        )

    def search(
        self,
        query: str,
        *,
        allowed_content_ids: Sequence[int],
        filters: PlaceSearchFilters,
        top_k: int,
    ) -> list[VectorCandidate]:
        query = query.strip()
        if not query:
            raise ValueError("query must not be blank")
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")
        if not allowed_content_ids:
            return []

        collection = get_collection_if_exists(
            self._client, self.config.collection_name
        )
        if collection is None:
            raise PlaceVectorSearchError(
                f"Chroma collection does not exist: {self.config.collection_name}"
            )
        self._validate_collection(collection)

        embeddings = self._embedder.embed([query])
        if len(embeddings) != 1 or not embeddings[0]:
            raise PlaceVectorSearchError(
                "embedding provider did not return one query embedding"
            )

        result = collection.query(
            query_embeddings=embeddings,
            n_results=min(top_k, len(allowed_content_ids)),
            where=_build_chroma_where(allowed_content_ids, filters),
            include=["documents", "metadatas", "distances"],
        )
        return _vector_candidates(result)

    def _validate_collection(self, collection: Any) -> None:
        metadata = collection.metadata or {}
        stored_model = str(metadata.get("embedding_model") or "")
        if stored_model and stored_model != self._embedder.model:
            raise PlaceVectorSearchError(
                "query embedding model does not match the Chroma collection: "
                f"{self._embedder.model} != {stored_model}"
            )


def _build_chroma_where(
    allowed_content_ids: Sequence[int],
    filters: PlaceSearchFilters,
) -> dict[str, Any]:
    clauses: list[dict[str, Any]] = []
    content_ids = [str(content_id) for content_id in allowed_content_ids]
    clauses.append(_value_filter("contentid", content_ids))

    for field_name, values in (
        ("dataset", filters.datasets),
        ("target_collection", filters.target_collections),
        ("place_subtype", filters.place_subtypes),
        ("itinerary_role", filters.itinerary_roles),
        ("recommendation_scope", filters.recommendation_scopes),
        ("city", filters.cities),
        ("district", filters.districts),
    ):
        if values:
            clauses.append(_value_filter(field_name, list(values)))

    for field_name, value in (
        ("route_eligible", filters.route_eligible),
        ("schedule_eligible", filters.schedule_eligible),
        ("requires_verification", filters.requires_verification),
    ):
        if value is not None:
            clauses.append({field_name: value})

    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _value_filter(field_name: str, values: Sequence[str]) -> dict[str, Any]:
    if len(values) == 1:
        return {field_name: values[0]}
    return {field_name: {"$in": list(values)}}


def _vector_candidates(result: Mapping[str, Any]) -> list[VectorCandidate]:
    ids = _first_result_list(result, "ids")
    documents = _first_result_list(result, "documents")
    metadatas = _first_result_list(result, "metadatas")
    distances = _first_result_list(result, "distances")

    candidates: list[VectorCandidate] = []
    for index, document_id in enumerate(ids):
        metadata = dict(_at(metadatas, index, {}) or {})
        raw_content_id = metadata.get("contentid") or str(document_id).split(":")[-1]
        try:
            content_id = int(raw_content_id)
            distance = float(_at(distances, index, 0.0))
        except (TypeError, ValueError) as exc:
            raise PlaceVectorSearchError(
                f"invalid Chroma result for document {document_id}"
            ) from exc
        candidates.append(
            VectorCandidate(
                content_id=content_id,
                document_id=str(document_id),
                distance=distance,
                similarity_score=1.0 - distance,
                document=str(_at(documents, index, "") or ""),
                metadata=metadata,
            )
        )
    return candidates


def _first_result_list(result: Mapping[str, Any], key: str) -> list[Any]:
    value = result.get(key) or []
    if not value:
        return []
    first = value[0]
    return list(first) if isinstance(first, (list, tuple)) else list(value)


def _at(values: Sequence[Any], index: int, default: Any) -> Any:
    return values[index] if index < len(values) else default
