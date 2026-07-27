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
