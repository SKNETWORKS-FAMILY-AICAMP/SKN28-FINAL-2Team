from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tour_recommender.embeddings.vector_store import ChromaPlaceRepository
from tour_recommender.rag.retriever import HybridPlaceRetriever
from tour_recommender.storage.mysql_repository import MySQLPlaceRepository
from tour_recommender.storage.config import ChromaConfig, MySQLConfig, StorageConfigError
from mysql.connector import Error as MySQLError


DEFAULT_ENV = PROJECT_ROOT / ".env"
DEFAULT_RAW = PROJECT_ROOT / "data" / "raw" / "korea_tour_openapi_jeju_places.csv"
DEFAULT_RAG = PROJECT_ROOT / "data" / "processed" / "jeju_place_rag_documents.json"
DEFAULT_LCLS = PROJECT_ROOT / "data" / "raw" / "korea_tour_openapi_lcls_codes.csv"
DEFAULT_RULES = PROJECT_ROOT / "configs" / "place_rules.json"
DEFAULT_SCHEMA = PROJECT_ROOT / "sql" / "mysql_schema.sql"


def main() -> int:
    parser = argparse.ArgumentParser(description="Load and search Jeju place storage.")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    commands = parser.add_subparsers(dest="command", required=True)

    load = commands.add_parser(
        "mysql-load", help="Create schema and load the TourAPI CSV plus RAG JSON."
    )
    load.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    load.add_argument("--rag", type=Path, default=DEFAULT_RAG)
    load.add_argument("--lcls", type=Path, default=DEFAULT_LCLS)
    load.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    load.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    load.add_argument("--batch-size", type=int, default=200)
    load.add_argument(
        "--recreate-database",
        action="store_true",
        help="Drop MYSQL_DATABASE before creating the approved schema.",
    )

    commands.add_parser("mysql-status", help="Show MySQL storage counts.")
    commands.add_parser("chroma-status", help="Show the Chroma collection count.")
    commands.add_parser(
        "aihub-chroma-status", help="Show the AIHub travel-profile collection count."
    )
    mysql_search = commands.add_parser("mysql-search", help="Search MySQL FULLTEXT.")
    _add_search_arguments(mysql_search)

    chroma_search = commands.add_parser("chroma-search", help="Search Chroma vectors.")
    _add_search_arguments(chroma_search)
    aihub_chroma_search = commands.add_parser(
        "aihub-chroma-search", help="Search AIHub travel-profile vectors."
    )
    _add_search_arguments(aihub_chroma_search)

    hybrid_search = commands.add_parser("hybrid-search", help="Search MySQL and Chroma.")
    _add_search_arguments(hybrid_search)
    hybrid_search.add_argument("--bm25-weight", type=float, default=0.7)
    hybrid_search.add_argument("--cosine-weight", type=float, default=0.3)
    hybrid_search.add_argument("--candidate-k", type=int, default=50)

    args = parser.parse_args()
    try:
        result = _run(args)
    except (OSError, ValueError, RuntimeError, StorageConfigError, MySQLError) as exc:
        message = str(exc).strip() or exc.__class__.__name__
        print(f"Error: {message}", file=sys.stderr)
        return 1
    _print_json(result)
    return 0


def _run(args: argparse.Namespace) -> object:
    if args.command.startswith("mysql") or args.command == "hybrid-search":
        mysql = MySQLPlaceRepository(MySQLConfig.from_env(args.env_file))
    chroma_commands = {
        "chroma-status",
        "chroma-search",
        "aihub-chroma-status",
        "aihub-chroma-search",
        "hybrid-search",
    }
    if args.command in chroma_commands:
        chroma_config = ChromaConfig.from_env(
            args.env_file, project_root=PROJECT_ROOT
        )
        if args.command.startswith("aihub-"):
            chroma_config = replace(
                chroma_config,
                collection_name=os.getenv(
                    "AIHUB_CHROMA_COLLECTION", "aihub_travel_profiles"
                ),
            )
        chroma = ChromaPlaceRepository(chroma_config)

    if args.command == "mysql-load":
        if args.recreate_database:
            mysql.recreate_database()
        mysql.apply_schema(args.schema)
        lcls_csv_path = args.lcls if args.lcls.exists() else None
        return asdict(
            mysql.load_places(
                args.raw,
                args.rag,
                lcls_csv_path=lcls_csv_path,
                rules_path=args.rules,
                batch_size=args.batch_size,
            )
        )
    if args.command == "mysql-status":
        return mysql.counts()
    if args.command in {"chroma-status", "aihub-chroma-status"}:
        metadata = chroma.collection.metadata or {}
        return {
            "collection": chroma.collection.name,
            "collection_records": chroma.count(),
            "embedding_model": metadata.get("embedding_model"),
            "embedding_dimensions": metadata.get("embedding_dimensions"),
            "preprocessing_version": metadata.get("preprocessing_version"),
        }
    if args.command == "mysql-search":
        return mysql.search_fulltext(
            args.query,
            target_collection=args.target_collection,
            dataset=args.dataset,
            limit=args.limit,
        )
    if args.command in {"chroma-search", "aihub-chroma-search"}:
        filters = {
            key: value
            for key, value in {
                "target_collection": args.target_collection,
                "dataset": args.dataset,
            }.items()
            if value is not None
        }
        return [
            asdict(result)
            for result in chroma.search(args.query, filters=filters, top_k=args.limit)
        ]
    retriever = HybridPlaceRetriever(mysql, chroma)
    return [
        asdict(result)
        for result in retriever.search(
            args.query,
            target_collection=args.target_collection,
            dataset=args.dataset,
            bm25_weight=args.bm25_weight,
            cosine_weight=args.cosine_weight,
            candidate_k=args.candidate_k,
            top_k=args.limit,
        )
    ]


def _add_search_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("query")
    parser.add_argument("--target-collection")
    parser.add_argument("--dataset")
    parser.add_argument("--limit", type=int, default=10)


def _print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    raise SystemExit(main())
