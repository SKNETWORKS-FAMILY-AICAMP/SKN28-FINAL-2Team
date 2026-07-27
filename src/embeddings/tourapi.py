from __future__ import annotations

from typing import Sequence

from src.common.paths import REPOSITORY_ROOT, TOURAPI_DATA_ROOT, VECTORSTORE_ROOT
from src.embeddings.cli import VectorIndexDefaults, run_vector_index_cli
from src.storage.tourapi import TOURAPI_CHROMA_COLLECTION


def run_tourapi_vector_index(
    argv: Sequence[str] | None = None,
) -> int:
    return run_vector_index_cli(
        VectorIndexDefaults(
            description=(
                "Embed the TourAPI Jeju place documents with OpenAI and persist "
                "them in ChromaDB."
            ),
            input_path=(
                TOURAPI_DATA_ROOT
                / "processed"
                / "jeju_place_rag_documents.json"
            ),
            persist_directory=VECTORSTORE_ROOT,
            collection_name=TOURAPI_CHROMA_COLLECTION,
            env_file=REPOSITORY_ROOT / ".env",
        ),
        argv,
    )
