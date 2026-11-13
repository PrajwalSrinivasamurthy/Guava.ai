"""In-memory stand-ins for the embedder and the index, so ingestion and retrieval are
tested without OpenAI or a database."""

import math

from kb_service.domain import KnowledgeDocument

VOCABULARY = ["textbook", "tuition", "password", "canvas", "transcript"]


class FakeEmbedder:
    """Embeds a text as keyword counts, so texts about the same topic land close together."""

    def __init__(self):
        self.embedded: list[str] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.embedded.extend(texts)
        return [[float(text.lower().count(word)) for word in VOCABULARY] for text in texts]


class InMemoryIndex:
    def __init__(self):
        self.documents: dict[str, tuple[str, list[str], list[list[float]]]] = {}

    def fingerprints(self) -> dict[str, str]:
        return {id_: fingerprint for id_, (fingerprint, _, _) in self.documents.items()}

    def replace_document(self, document_id, fingerprint, chunks, vectors) -> None:
        self.documents[document_id] = (fingerprint, list(chunks), [list(v) for v in vectors])

    def delete_documents(self, document_ids) -> None:
        for id_ in document_ids:
            self.documents.pop(id_, None)

    def search(self, vector, limit) -> list[str]:
        scored = [
            (_cosine(vector, stored), chunk)
            for _, chunks, vectors in self.documents.values()
            for chunk, stored in zip(chunks, vectors)
        ]
        return [chunk for _, chunk in sorted(scored, key=lambda pair: pair[0], reverse=True)[:limit]]


class StaticSource:
    def __init__(self, *documents: KnowledgeDocument):
        self._documents = list(documents)

    def documents(self):
        return iter(self._documents)


def _cosine(a: list[float], b: list[float]) -> float:
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / norm if norm else 0.0
