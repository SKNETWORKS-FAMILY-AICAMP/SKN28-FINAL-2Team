from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.embeddings.embedder import OpenAIEmbeddingClient, OpenAIEmbeddingError
from src.embeddings.indexer import (
    ChromaIndexError,
    RagDataset,
    RagDocument,
    compute_document_hash,
    index_rag_dataset,
    load_rag_dataset,
    sanitize_metadata,
)


class FakeEmbeddingsEndpoint:
    def __init__(self, data) -> None:
        self.data = data
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(data=self.data)


class FakeOpenAIClient:
    def __init__(self, data) -> None:
        self.embeddings = FakeEmbeddingsEndpoint(data)


class FakeEmbedder:
    model = "fake-model"
    dimensions = 3

    def __init__(self) -> None:
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeCollection:
    def __init__(self, metadatas) -> None:
        self.metadata = {
            "embedding_model": "fake-model",
            "embedding_dimensions": 3,
        }
        self.ids = set(metadatas)
        self.metadatas = metadatas
        self.upserts = []
        self.deleted = []
        self.modified = None

    def count(self):
        return len(self.ids)

    def get(self, include):
        ids = list(self.metadatas)
        return {"ids": ids, "metadatas": [self.metadatas[item] for item in ids]}

    def upsert(self, **kwargs):
        self.upserts.append(kwargs)
        self.ids.update(kwargs["ids"])

    def delete(self, *, ids):
        self.deleted.extend(ids)
        self.ids.difference_update(ids)

    def modify(self, *, metadata):
        self.modified = metadata
        self.metadata = metadata


class EmbeddingClientTests(unittest.TestCase):
    def test_validates_constructor_inputs(self) -> None:
        with self.assertRaises(ValueError):
            OpenAIEmbeddingClient(api_key="", client=FakeOpenAIClient([]))
        with self.assertRaises(ValueError):
            OpenAIEmbeddingClient(api_key="key", model=" ", client=FakeOpenAIClient([]))
        with self.assertRaises(ValueError):
            OpenAIEmbeddingClient(api_key="key", dimensions=0, client=FakeOpenAIClient([]))

    def test_empty_input_returns_without_api_call(self) -> None:
        fake = FakeOpenAIClient([])
        client = OpenAIEmbeddingClient(api_key="key", client=fake)
        self.assertEqual(client.embed([]), [])
        self.assertEqual(fake.embeddings.calls, [])

    def test_rejects_blank_input(self) -> None:
        client = OpenAIEmbeddingClient(api_key="key", client=FakeOpenAIClient([]))
        with self.assertRaisesRegex(ValueError, "blank text"):
            client.embed(["제주", " "])

    def test_orders_response_by_index_and_sends_dimensions(self) -> None:
        fake = FakeOpenAIClient(
            [
                SimpleNamespace(index=1, embedding=[4.0, 5.0, 6.0]),
                SimpleNamespace(index=0, embedding=[1.0, 2.0, 3.0]),
            ]
        )
        client = OpenAIEmbeddingClient(api_key="key", dimensions=3, client=fake)

        result = client.embed(["첫째", "둘째"])

        self.assertEqual(result, [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        self.assertEqual(fake.embeddings.calls[0]["dimensions"], 3)
        self.assertEqual(fake.embeddings.calls[0]["encoding_format"], "float")

    def test_rejects_wrong_count_and_inconsistent_dimensions(self) -> None:
        count_client = OpenAIEmbeddingClient(
            api_key="key",
            client=FakeOpenAIClient([SimpleNamespace(index=0, embedding=[1.0])]),
        )
        with self.assertRaisesRegex(OpenAIEmbeddingError, "1 embeddings for 2"):
            count_client.embed(["a", "b"])

        dimension_client = OpenAIEmbeddingClient(
            api_key="key",
            client=FakeOpenAIClient(
                [
                    SimpleNamespace(index=0, embedding=[1.0]),
                    SimpleNamespace(index=1, embedding=[1.0, 2.0]),
                ]
            ),
        )
        with self.assertRaisesRegex(OpenAIEmbeddingError, "inconsistent"):
            dimension_client.embed(["a", "b"])


class IndexerTests(unittest.TestCase):
    def test_load_dataset_validates_and_hashes_documents(self) -> None:
        payload = {
            "preprocessing_version": "v1",
            "schema_version": "v2",
            "documents": [
                {"id": "1", "embedding_text": "제주 바다", "metadata": {"city": "제주"}}
            ],
        }
        with patch(
            "src.embeddings.indexer.Path.read_text",
            return_value=json.dumps(payload, ensure_ascii=False),
        ):
            dataset = load_rag_dataset("rag.json")

        self.assertEqual(dataset.preprocessing_version, "v1")
        self.assertEqual(dataset.schema_version, "v2")
        self.assertEqual(
            dataset.documents[0].document_hash,
            compute_document_hash("제주 바다", {"city": "제주"}),
        )

    def test_load_dataset_rejects_duplicate_ids(self) -> None:
        payload = {
            "documents": [
                {"id": "1", "embedding_text": "a", "metadata": {}},
                {"id": "1", "embedding_text": "b", "metadata": {}},
            ]
        }
        with patch(
            "src.embeddings.indexer.Path.read_text",
            return_value=json.dumps(payload),
        ):
            with self.assertRaisesRegex(ChromaIndexError, "duplicate document id"):
                load_rag_dataset("rag.json")

    def test_sanitize_metadata_keeps_scalars_and_serializes_nested_values(self) -> None:
        result = sanitize_metadata(
            {"none": None, "name": "제주", "tags": ["바다", "자연"], "nested": {"a": 1}}
        )
        self.assertNotIn("none", result)
        self.assertEqual(result["tags"], ["바다", "자연"])
        self.assertEqual(result["nested"], '{"a": 1}')

    def test_index_skips_unchanged_upserts_changed_and_prunes_stale(self) -> None:
        first = RagDocument("1", "같음", {}, compute_document_hash("같음", {}))
        second = RagDocument("2", "새 문서", {}, compute_document_hash("새 문서", {}))
        dataset = RagDataset((first, second), "v1", "v1")
        collection = FakeCollection(
            {
                "1": {
                    "document_hash": first.document_hash,
                    "embedding_model": "fake-model",
                    "embedding_dimensions": 3,
                },
                "stale": {
                    "document_hash": "old",
                    "embedding_model": "fake-model",
                    "embedding_dimensions": 3,
                },
            }
        )
        embedder = FakeEmbedder()

        with patch("src.embeddings.indexer.get_collection_if_exists", return_value=collection):
            summary = index_rag_dataset(
                dataset,
                persist_directory="unused",
                collection_name="places",
                embedder=embedder,
                prune=True,
                client=object(),
            )

        self.assertEqual(embedder.calls, [["새 문서"]])
        self.assertEqual(collection.upserts[0]["ids"], ["2"])
        self.assertEqual(collection.deleted, ["stale"])
        self.assertEqual(summary.skipped_count, 1)
        self.assertEqual(summary.upserted_count, 1)
        self.assertEqual(summary.pruned_count, 1)
        self.assertEqual(summary.collection_count, 2)


if __name__ == "__main__":
    unittest.main()
