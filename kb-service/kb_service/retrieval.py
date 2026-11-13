"""Finding the passages that answer a question."""

from kb_service.interfaces import Embedder, VectorIndex


class IndexRetriever:
    def __init__(self, embedder: Embedder, index: VectorIndex):
        self._embedder = embedder
        self._index = index

    def search(self, question: str, limit: int) -> list[str]:
        vector = self._embedder.embed([question])[0]
        return self._index.search(vector, limit)
