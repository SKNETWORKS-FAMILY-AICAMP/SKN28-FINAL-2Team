from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tour_recommender.embeddings.indexer import (
    ChromaIndexError,
    index_rag_dataset,
    load_rag_dataset,
)
from tour_recommender.embeddings.embedder import (
    DEFAULT_EMBEDDING_MODEL,
    OpenAIEmbeddingClient,
    OpenAIEmbeddingError,
)
from tour_recommender.utils.config import load_env_file


DEFAULT_INPUT = PROJECT_ROOT / "data" / "processed" / "jeju_place_rag_documents.json"
DEFAULT_PERSIST_DIRECTORY = PROJECT_ROOT / "data" / "chroma"
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Embed the Jeju RAG documents with OpenAI and persist them in ChromaDB."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--persist-dir", type=Path, default=DEFAULT_PERSIST_DIRECTORY)
    parser.add_argument("--collection", default="jeju_places")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument(
        "--model",
        help=f"OpenAI embedding model (default: {DEFAULT_EMBEDDING_MODEL})",
    )
    parser.add_argument("--dimensions", type=int)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete and rebuild the named collection. This repeats embedding costs.",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Delete collection records that are absent from the input JSON.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the JSON without calling OpenAI or changing ChromaDB.",
    )
    args = parser.parse_args()

    try:
        load_env_file(args.env_file)
        model = args.model or os.environ.get(
            "OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL
        )
        dataset = load_rag_dataset(args.input)
        if args.dry_run:
            print("Chroma index dry run")
            print(f"  input: {args.input}")
            print(f"  documents: {len(dataset.documents)}")
            print(f"  preprocessing version: {dataset.preprocessing_version}")
            print(f"  model: {model}")
            return 0

        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError(
                f"OPENAI_API_KEY is not set in the environment or {args.env_file}"
            )
        embedder = OpenAIEmbeddingClient(
            api_key=api_key,
            model=model,
            dimensions=args.dimensions,
        )
        summary = index_rag_dataset(
            dataset,
            persist_directory=args.persist_dir,
            collection_name=args.collection,
            embedder=embedder,
            batch_size=args.batch_size,
            recreate=args.recreate,
            prune=args.prune,
            progress=lambda completed, total: print(
                f"[chroma] checkpoint: {completed}/{total}"
            ),
        )
    except (OSError, ValueError, ChromaIndexError, OpenAIEmbeddingError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("Chroma index complete")
    print(f"  input documents: {summary.input_count}")
    print(f"  embedded/upserted: {summary.upserted_count}")
    print(f"  unchanged/skipped: {summary.skipped_count}")
    print(f"  pruned: {summary.pruned_count}")
    print(f"  collection records: {summary.collection_count}")
    print(f"  embedding dimensions: {summary.embedding_dimensions}")
    print(f"  persist directory: {args.persist_dir}")
    print(f"  collection: {args.collection}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
