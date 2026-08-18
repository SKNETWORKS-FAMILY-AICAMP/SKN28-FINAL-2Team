"""Verify that the deployed Chroma collection matches the release RAG artifact."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.common.env import load_env_file
from src.common.paths import TOURAPI_DATA_ROOT
from src.embeddings.embedder import DEFAULT_EMBEDDING_MODEL
from src.embeddings.indexer import load_rag_dataset
from src.storage.chroma import verify_chroma_collection
from src.storage.tourapi import chroma_config_from_env


DEFAULT_INPUT = TOURAPI_DATA_ROOT / "processed" / "jeju_place_rag_documents.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=REPOSITORY_ROOT / ".env")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args(argv)

    try:
        load_env_file(args.env_file)
        dataset = load_rag_dataset(args.input)
        config = chroma_config_from_env(project_root=REPOSITORY_ROOT)
        result = verify_chroma_collection(
            config,
            expected_count=len(dataset.documents),
            expected_model=os.getenv("OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
            expected_preprocessing_version=dataset.preprocessing_version,
            expected_schema_version=dataset.schema_version,
        )
        print(json.dumps({"status": "ok", **result}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {"status": "failed", "error": str(exc) or exc.__class__.__name__},
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
