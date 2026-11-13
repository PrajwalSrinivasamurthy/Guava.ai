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


class Retriever(Protocol):
    """Finds the passages most relevant to a question, best first."""

    def search(self, question: str, limit: int) -> list[str]: ...


class Answerer(Protocol):
    """Turns a question into an Answer."""

    def answer(self, question: str) -> Answer: ...
