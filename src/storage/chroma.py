"""Shared Chroma client and collection access helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config.settings import ChromaConfig


def create_chroma_client(config: ChromaConfig) -> Any:
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError(
            "chromadb is not installed; run: pip install -r requirements.txt"
        ) from exc

    if config.mode == "http":
        return chromadb.HttpClient(host=config.host, port=config.port, ssl=config.ssl)

    return create_persistent_chroma_client(config.persist_directory)


def create_persistent_chroma_client(path: str | Path) -> Any:
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError(
            "chromadb is not installed; run: pip install -r requirements.txt"
        ) from exc
    persist_directory = Path(path)
    persist_directory.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(persist_directory.resolve()))


def get_collection_if_exists(client: Any, collection_name: str) -> Any | None:
    names = {collection.name for collection in client.list_collections()}
    if collection_name not in names:
        return None
    return client.get_collection(collection_name, embedding_function=None)


def verify_chroma_collection(
    config: ChromaConfig,
    *,
    expected_count: int | None = None,
    expected_model: str | None = None,
    expected_preprocessing_version: str | None = None,
    expected_schema_version: str | None = None,
) -> dict[str, Any]:
    """Check server reachability and the deployed collection contract."""

    client = create_chroma_client(config)
    client.heartbeat()
    collection = get_collection_if_exists(client, config.collection_name)
    if collection is None:
        raise RuntimeError(f"Chroma collection '{config.collection_name}' does not exist")

    count = int(collection.count())
    metadata = collection.metadata or {}
    if count <= 0:
        raise RuntimeError(f"Chroma collection '{config.collection_name}' is empty")
    if expected_count is not None and count != expected_count:
        raise RuntimeError(
            f"Chroma record count mismatch: expected={expected_count}, actual={count}"
        )

    checks = {
        "embedding_model": expected_model,
        "preprocessing_version": expected_preprocessing_version,
        "schema_version": expected_schema_version,
    }
    for name, expected in checks.items():
        if expected is not None and str(metadata.get(name) or "") != expected:
            raise RuntimeError(
                f"Chroma {name} mismatch: expected={expected}, "
                f"actual={metadata.get(name)}"
            )

    try:
        source_count = int(metadata.get("source_document_count"))
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Chroma source_document_count metadata is missing") from exc
    if source_count != count:
        raise RuntimeError(
            f"Chroma source count mismatch: metadata={source_count}, actual={count}"
        )

    return {
        "collection": config.collection_name,
        "records": count,
        "embedding_model": metadata.get("embedding_model"),
        "embedding_dimensions": metadata.get("embedding_dimensions"),
        "preprocessing_version": metadata.get("preprocessing_version"),
        "schema_version": metadata.get("schema_version"),
    }
