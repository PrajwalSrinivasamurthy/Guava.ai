"""The seams between the service's parts.

Each is a Protocol, so an implementation only has to have the right methods: a test
fake, a different database, or a different document format can be swapped in without
touching the code that uses it.
"""

from typing import Iterable, Protocol

from kb_service.domain import Answer, KnowledgeDocument


class DocumentSource(Protocol):
    """Where knowledge documents come from (a folder of files, a database, ...)."""

    def documents(self) -> Iterable[KnowledgeDocument]: ...


class Embedder(Protocol):
    """Turns texts into vectors that capture their meaning. Documents and questions are
    embedded the same way, so one method serves both."""

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class VectorIndex(Protocol):
    """Stores document passages with their vectors and finds the closest to a vector.

    Each document is stored under its id with a fingerprint of the content it was built
    from, which is how ingestion tells which documents have changed.
    """

    def fingerprints(self) -> dict[str, str]: ...

    def replace_document(
        self, document_id: str, fingerprint: str, chunks: list[str], vectors: list[list[float]]
    ) -> None: ...

    def delete_documents(self, document_ids: list[str]) -> None: ...

    def search(self, vector: list[float], limit: int) -> list[str]: ...


class Retriever(Protocol):
    """Finds the passages most relevant to a question, best first."""

    def search(self, question: str, limit: int) -> list[str]: ...


class Answerer(Protocol):
    """Turns a question into an Answer."""

    def answer(self, question: str) -> Answer: ...
