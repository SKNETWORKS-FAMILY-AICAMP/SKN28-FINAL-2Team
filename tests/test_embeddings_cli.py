from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.embeddings.cli import VectorIndexDefaults, run_vector_index_cli


class VectorIndexCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.defaults = VectorIndexDefaults(
            description="test index",
            input_path=Path("rag.json"),
            persist_directory=Path("vectorstore"),
            collection_name="places",
            env_file=Path(".env.test"),
        )
        self.dataset = SimpleNamespace(
            documents=(object(),),
            preprocessing_version="test-v1",
        )
        self.summary = SimpleNamespace(
            input_count=1,
            upserted_count=1,
            skipped_count=0,
            pruned_count=0,
            collection_count=1,
            embedding_dimensions=3,
        )

    def test_http_mode_indexes_through_http_client(self) -> None:
        http_client = object()

        with (
            patch.dict(
                os.environ,
                {
                    "OPENAI_API_KEY": "test-key",
                    "CHROMA_MODE": "http",
                    "CHROMA_HOST": "chromadb",
                    "CHROMA_PORT": "8000",
                    "CHROMA_SSL": "false",
                },
                clear=True,
            ),
            patch("src.embeddings.cli.load_env_file"),
            patch(
                "src.embeddings.cli.load_rag_dataset",
                return_value=self.dataset,
            ),
            patch("src.embeddings.cli.OpenAIEmbeddingClient"),
            patch(
                "src.embeddings.cli.create_chroma_client",
                return_value=http_client,
            ) as create_client,
            patch(
                "src.embeddings.cli.index_rag_dataset",
                return_value=self.summary,
            ) as index_dataset,
            redirect_stdout(StringIO()),
        ):
            result = run_vector_index_cli(self.defaults, [])

        self.assertEqual(result, 0)
        create_client.assert_called_once()
        self.assertEqual(
            index_dataset.call_args.kwargs["client"],
            http_client,
        )

    def test_persistent_mode_preserves_embedded_client_behavior(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "OPENAI_API_KEY": "test-key",
                    "CHROMA_MODE": "persistent",
                },
                clear=True,
            ),
            patch("src.embeddings.cli.load_env_file"),
            patch(
                "src.embeddings.cli.load_rag_dataset",
                return_value=self.dataset,
            ),
            patch("src.embeddings.cli.OpenAIEmbeddingClient"),
            patch(
                "src.embeddings.cli.create_chroma_client",
            ) as create_client,
            patch(
                "src.embeddings.cli.index_rag_dataset",
                return_value=self.summary,
            ) as index_dataset,
            redirect_stdout(StringIO()),
        ):
            result = run_vector_index_cli(self.defaults, [])

        self.assertEqual(result, 0)
        create_client.assert_not_called()
        self.assertIsNone(index_dataset.call_args.kwargs["client"])


if __name__ == "__main__":
    unittest.main()
