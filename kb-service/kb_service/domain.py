"""The two data types every other module shares."""

from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeDocument:
    """One source document. The id is stable across edits, so re-ingesting a changed
    document replaces it instead of duplicating it."""

    id: str
    text: str


@dataclass(frozen=True)
class Answer:
    """What the service returns for a question. When found is False, text is empty and
    the caller supplies its own wording."""

    found: bool
    text: str = ""

    @classmethod
    def not_found(cls) -> "Answer":
        return cls(found=False)
