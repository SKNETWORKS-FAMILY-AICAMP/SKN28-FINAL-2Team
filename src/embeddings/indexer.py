from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Protocol

from ..storage.chroma import create_persistent_chroma_client, get_collection_if_exists


class EmbeddingProvider(Protocol):
    model: str
    dimensions: int | None

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class ChromaIndexError(RuntimeError):
    """Raised when a RAG payload cannot be indexed safely."""


@dataclass(frozen=True)
class RagDocument:
    document_id: str
    text: str
    metadata: dict[str, Any]
    document_hash: str


@dataclass(frozen=True)
class RagDataset:
    documents: tuple[RagDocument, ...]
    preprocessing_version: str
    schema_version: str


@dataclass(frozen=True)
class ChromaIndexSummary:
    input_count: int
    embedded_count: int
    skipped_count: int
    upserted_count: int
    pruned_count: int
    collection_count: int
    embedding_dimensions: int


ProgressCallback = Callable[[int, int], None]


def load_rag_dataset(path: str | Path) -> RagDataset:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ChromaIndexError("RAG JSON root must be an object")

    raw_documents = payload.get("documents")
    if not isinstance(raw_documents, list) or not raw_documents:
        raise ChromaIndexError("RAG JSON must contain a non-empty documents list")

    documents: list[RagDocument] = []
    seen_ids: set[str] = set()
    for index, raw_document in enumerate(raw_documents):
        if not isinstance(raw_document, Mapping):
            raise ChromaIndexError(f"documents[{index}] must be an object")
        document_id = str(raw_document.get("id") or "").strip()
        text = str(raw_document.get("embedding_text") or "").strip()
        metadata = raw_document.get("metadata")
        if not document_id:
            raise ChromaIndexError(f"documents[{index}] has a blank id")
        if document_id in seen_ids:
            raise ChromaIndexError(f"duplicate document id: {document_id}")
        if not text:
            raise ChromaIndexError(f"document {document_id} has blank embedding_text")
        if not isinstance(metadata, Mapping):
            raise ChromaIndexError(f"document {document_id} metadata must be an object")

        normalized_metadata = dict(metadata)
        document_hash = compute_document_hash(text, normalized_metadata)
        documents.append(
            RagDocument(document_id, text, normalized_metadata, document_hash)
        )
        seen_ids.add(document_id)

    return RagDataset(
        documents=tuple(documents),
        preprocessing_version=str(payload.get("preprocessing_version") or "unknown"),
        schema_version=str(payload.get("schema_version") or "unknown"),
    )


def index_rag_dataset(
    dataset: RagDataset,
    *,
    persist_directory: str | Path,
    collection_name: str,
    embedder: EmbeddingProvider,
    batch_size: int = 100,
    recreate: bool = False,
    prune: bool = False,
    progress: ProgressCallback | None = None,
    client: Any | None = None,
) -> ChromaIndexSummary:
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")
    if not collection_name.strip():
        raise ValueError("collection_name is empty")

    if client is None:
        client = create_persistent_chroma_client(persist_directory)

    collection = get_collection_if_exists(client, collection_name)
    if recreate and collection is not None:
        client.delete_collection(collection_name)
        collection = None

    existing_metadata: dict[str, Mapping[str, Any]] = {}
    collection_dimensions: int | None = None
    if collection is not None:
        collection_dimensions = _validate_collection(collection, embedder)
        existing_metadata = _existing_metadata(collection)

    pending = [
        document
        for document in dataset.documents
        if not _is_unchanged(document, existing_metadata.get(document.document_id), embedder)
    ]
    skipped_count = len(dataset.documents) - len(pending)
    upserted_count = 0

    for batch in _batches(pending, batch_size):
        embeddings = embedder.embed([document.text for document in batch])
        if len(embeddings) != len(batch):
            raise ChromaIndexError(
                f"embedder returned {len(embeddings)} embeddings for {len(batch)} documents"
            )
        batch_dimensions = _embedding_dimensions(embeddings)
        if collection_dimensions is not None and batch_dimensions != collection_dimensions:
            raise ChromaIndexError(
                "embedding dimension does not match the existing collection: "
                f"{batch_dimensions} != {collection_dimensions}"
            )
        collection_dimensions = batch_dimensions

        if collection is None:
            collection = client.get_or_create_collection(
                collection_name,
                metadata=_collection_metadata(
                    dataset, embedder, collection_dimensions, include_distance=True
                ),
                embedding_function=None,
            )

        collection.upsert(
            ids=[document.document_id for document in batch],
            documents=[document.text for document in batch],
            embeddings=embeddings,
            metadatas=[
                _chroma_metadata(document, embedder, collection_dimensions)
                for document in batch
            ],
        )
        upserted_count += len(batch)
        if progress is not None:
            progress(upserted_count, len(pending))

    if collection is None:
        raise ChromaIndexError("no documents were available to create the collection")

    if collection_dimensions is None:
        collection_dimensions = _stored_dimensions(collection.metadata)
    if collection_dimensions is None:
        raise ChromaIndexError("collection embedding dimensions are unknown")

    stale_ids = set(existing_metadata).difference(
        document.document_id for document in dataset.documents
    )
    if prune and stale_ids:
        collection.delete(ids=sorted(stale_ids))
    pruned_count = len(stale_ids) if prune else 0

    collection.modify(
        metadata=_collection_metadata(
            dataset,
            embedder,
            collection_dimensions,
            source_document_count=collection.count(),
        )
    )
    return ChromaIndexSummary(
        input_count=len(dataset.documents),
        embedded_count=len(pending),
        skipped_count=skipped_count,
        upserted_count=upserted_count,
        pruned_count=pruned_count,
        collection_count=collection.count(),
        embedding_dimensions=collection_dimensions,
    )


def sanitize_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            sanitized[str(key)] = value
            continue
        if isinstance(value, (list, tuple)):
            items = [item for item in value if item is not None]
            if not items:
                continue
            item_types = {type(item) for item in items}
            if len(item_types) == 1 and item_types.pop() in {str, int, float, bool}:
                sanitized[str(key)] = items
                continue
        sanitized[str(key)] = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return sanitized


def _validate_collection(collection: Any, embedder: EmbeddingProvider) -> int | None:
    metadata = collection.metadata or {}
    stored_model = str(metadata.get("embedding_model") or "")
    if collection.count() and not stored_model:
        raise ChromaIndexError(
            "existing collection has no embedding_model metadata; use --recreate"
        )
    if stored_model and stored_model != embedder.model:
        raise ChromaIndexError(
            f"collection uses {stored_model}, requested {embedder.model}; use --recreate"
        )

    stored_dimensions = _stored_dimensions(metadata)
    if (
        stored_dimensions is not None
        and embedder.dimensions is not None
        and stored_dimensions != embedder.dimensions
    ):
        raise ChromaIndexError(
            "collection embedding dimensions differ from the requested dimensions; "
            "use --recreate"
        )
    return stored_dimensions


def _stored_dimensions(metadata: Mapping[str, Any] | None) -> int | None:
    if not metadata:
        return None
    value = metadata.get("embedding_dimensions")
    try:
        dimensions = int(value)
    except (TypeError, ValueError):
        return None
    return dimensions if dimensions > 0 else None


def _existing_metadata(collection: Any) -> dict[str, Mapping[str, Any]]:
    result = collection.get(include=["metadatas"])
    metadatas = result.get("metadatas") or []
    return {
        document_id: metadata or {}
        for document_id, metadata in zip(result.get("ids") or [], metadatas, strict=True)
    }


def _is_unchanged(
    document: RagDocument,
    existing: Mapping[str, Any] | None,
    embedder: EmbeddingProvider,
) -> bool:
    if not existing:
        return False
    if existing.get("document_hash") != document.document_hash:
        return False
    if existing.get("embedding_model") != embedder.model:
        return False
    if embedder.dimensions is None:
        return True
    try:
        return int(existing.get("embedding_dimensions")) == embedder.dimensions
    except (TypeError, ValueError):
        return False


def _embedding_dimensions(embeddings: Sequence[Sequence[float]]) -> int:
    if not embeddings or not embeddings[0]:
        raise ChromaIndexError("embedder returned no embedding values")
    dimensions = len(embeddings[0])
    if any(len(embedding) != dimensions for embedding in embeddings):
        raise ChromaIndexError("embedder returned inconsistent embedding dimensions")
    return dimensions


def _chroma_metadata(
    document: RagDocument,
    embedder: EmbeddingProvider,
    dimensions: int,
) -> dict[str, Any]:
    return {
        **sanitize_metadata(document.metadata),
        "document_hash": document.document_hash,
        "embedding_model": embedder.model,
        "embedding_dimensions": dimensions,
    }


def _collection_metadata(
    dataset: RagDataset,
    embedder: EmbeddingProvider,
    dimensions: int,
    *,
    include_distance: bool = False,
    source_document_count: int | None = None,
) -> dict[str, Any]:
    metadata = {
        "embedding_model": embedder.model,
        "embedding_dimensions": dimensions,
        "preprocessing_version": dataset.preprocessing_version,
        "schema_version": dataset.schema_version,
        "source_document_count": (
            len(dataset.documents)
            if source_document_count is None
            else source_document_count
        ),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    if include_distance:
        metadata["hnsw:space"] = "cosine"
    return metadata


def compute_document_hash(text: str, metadata: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        {"embedding_text": text, "metadata": metadata},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _batches(items: Sequence[RagDocument], size: int) -> Iterator[Sequence[RagDocument]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]
