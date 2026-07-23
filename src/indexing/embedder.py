from __future__ import annotations

from collections.abc import Sequence
from typing import Any


DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


class OpenAIEmbeddingError(RuntimeError):
    """Raised when OpenAI does not return usable embeddings."""


class OpenAIEmbeddingClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_EMBEDDING_MODEL,
        dimensions: int | None = None,
        timeout: float = 60.0,
        max_retries: int = 5,
        client: Any | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("OPENAI_API_KEY is empty")
        if not model.strip():
            raise ValueError("embedding model is empty")
        if dimensions is not None and dimensions <= 0:
            raise ValueError("embedding dimensions must be greater than zero")

        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise OpenAIEmbeddingError(
                    "openai is not installed; run: pip install -r requirements.txt"
                ) from exc
            client = OpenAI(
                api_key=api_key,
                timeout=timeout,
                max_retries=max_retries,
            )

        self._client = client
        self.model = model
        self.dimensions = dimensions

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        inputs = list(texts)
        if not inputs:
            return []
        if any(not text.strip() for text in inputs):
            raise ValueError("embedding input contains blank text")

        request: dict[str, Any] = {
            "model": self.model,
            "input": inputs,
            "encoding_format": "float",
        }
        if self.dimensions is not None:
            request["dimensions"] = self.dimensions

        try:
            response = self._client.embeddings.create(**request)
        except Exception as exc:
            raise OpenAIEmbeddingError(f"OpenAI embedding request failed: {exc}") from exc

        ordered = sorted(response.data, key=lambda item: item.index)
        embeddings = [list(item.embedding) for item in ordered]
        if len(embeddings) != len(inputs):
            raise OpenAIEmbeddingError(
                f"OpenAI returned {len(embeddings)} embeddings for {len(inputs)} inputs"
            )
        if not embeddings or not embeddings[0]:
            raise OpenAIEmbeddingError("OpenAI returned an empty embedding")

        actual_dimensions = len(embeddings[0])
        if any(len(embedding) != actual_dimensions for embedding in embeddings):
            raise OpenAIEmbeddingError("OpenAI returned inconsistent embedding dimensions")
        if self.dimensions is not None and actual_dimensions != self.dimensions:
            raise OpenAIEmbeddingError(
                f"expected {self.dimensions} dimensions, got {actual_dimensions}"
            )
        return embeddings
