"""Check the Docker RAG dependencies without exposing credentials."""

from __future__ import annotations

import json
from pathlib import Path

from src.common.env import load_env_file
from src.config.settings import ChromaConfig, MySQLConfig
from src.storage.chroma import create_chroma_client, get_collection_if_exists


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_env_file(PROJECT_ROOT / ".env")


def mysql_counts() -> dict[str, int]:
    import mysql.connector

    config = MySQLConfig.from_env()
    connection = mysql.connector.connect(**config.connection_kwargs())
    cursor = connection.cursor()
    try:
        result: dict[str, int] = {}
        for table in ("places", "place_search_documents", "aihub_travel", "aihub_visit"):
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            result[table] = int(cursor.fetchone()[0])
        return result
    finally:
        cursor.close()
        connection.close()


def chroma_count() -> tuple[str, int]:
    config = ChromaConfig.from_env(project_root=PROJECT_ROOT)
    client = create_chroma_client(config)
    collection = get_collection_if_exists(client, config.collection_name)
    if collection is None:
        raise RuntimeError(
            f"Chroma collection does not exist: {config.collection_name}"
        )
    return config.collection_name, int(collection.count())


def main() -> int:
    mysql = mysql_counts()
    collection, documents = chroma_count()
    healthy = (
        all(count > 0 for count in mysql.values())
        and documents > 0
    )
    print(
        json.dumps(
            {
                "status": "ok" if healthy else "not_ready",
                "mysql": mysql,
                "chroma": {
                    "collection": collection,
                    "documents": documents,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
