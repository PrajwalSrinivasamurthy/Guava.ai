"""Embedding through the OpenAI API."""

from typing import Any


class OpenAIEmbedder:
    """Takes the OpenAI client as an argument, so tests can pass a fake and nothing here
    builds a client (or reads a key) on its own."""

    def __init__(self, client: Any, model: str, dimensions: int, batch_size: int = 64):
        self._client = client
        self._model = model
        self._dimensions = dimensions
        self._batch_size = batch_size

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start:start + self._batch_size]
            response = self._client.embeddings.create(
                model=self._model, input=batch, dimensions=self._dimensions
            )
            vectors.extend(item.embedding for item in sorted(response.data, key=lambda item: item.index))
        return vectors
