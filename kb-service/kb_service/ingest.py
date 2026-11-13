"""Keeps the index in step with a set of source documents.

sync() is idempotent: documents whose content hasn't changed are left alone (and not
re-embedded, which is what costs money), changed ones are replaced, new ones are added
and ones no longer in the source are removed. Run from the command line:

    uv run --env-file .env python -m kb_service.ingest path/to/documents [--dry-run]
"""

import argparse
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

from kb_service.chunker import chunk_text
from kb_service.domain import KnowledgeDocument
from kb_service.interfaces import DocumentSource, Embedder, VectorIndex


class EmptySourceError(Exception):
    """The source has no documents but the index does; likely the wrong folder."""


@dataclass(frozen=True)
class IngestReport:
    added: list[str]
    updated: list[str]
    removed: list[str]
    unchanged: list[str]


class Ingester:
    def __init__(
        self, index: VectorIndex, embedder: Embedder, *, chunk_size: int, chunk_overlap: int, signature: str
    ):
        """signature names the embedding setup (model and vector size). It is part of every
        document's fingerprint, so changing it re-embeds everything."""
        self._index = index
        self._embedder = embedder
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._signature = signature

    def sync(self, source: DocumentSource, *, dry_run: bool = False, allow_empty: bool = False) -> IngestReport:
        stored = self._index.fingerprints()
        documents = _unique(source.documents())
        if not documents and stored and not allow_empty:
            raise EmptySourceError(
                f"the source has no documents but the index holds {len(stored)}; "
                "check the path, or pass --allow-empty to clear the index"
            )

        added, updated, unchanged = [], [], []
        changed: list[tuple[KnowledgeDocument, str]] = []
        for document in documents:
            fingerprint = self._fingerprint(document)
            if document.id not in stored:
                added.append(document.id)
            elif stored[document.id] != fingerprint:
                updated.append(document.id)
            else:
                unchanged.append(document.id)
                continue
            changed.append((document, fingerprint))
        removed = sorted(set(stored) - {document.id for document in documents})

        if not dry_run:
            for document, fingerprint in changed:
                chunks = chunk_text(document.text, self._chunk_size, self._chunk_overlap)
                self._index.replace_document(document.id, fingerprint, chunks, self._embedder.embed(chunks))
            if removed:
                self._index.delete_documents(removed)
        return IngestReport(added, updated, removed, unchanged)

    def _fingerprint(self, document: KnowledgeDocument) -> str:
        basis = f"{self._signature}|{self._chunk_size}|{self._chunk_overlap}|{document.text}"
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def _unique(documents) -> list[KnowledgeDocument]:
    found = list(documents)
    ids = [document.id for document in found]
    duplicates = sorted({id_ for id_ in ids if ids.count(id_) > 1})
    if duplicates:
        raise ValueError(f"duplicate document ids: {', '.join(duplicates)}")
    return found


def main(argv: list[str] | None = None) -> int:
    from kb_service import wiring
    from kb_service.settings import ConfigError, Settings
    from kb_service.sources import DirectoryDocumentSource

    parser = argparse.ArgumentParser(description="Sync a folder of documents into the knowledge index.")
    parser.add_argument("folder", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="show what would change without changing it")
    parser.add_argument("--allow-empty", action="store_true", help="allow an empty folder to clear the index")
    args = parser.parse_args(argv)

    try:
        settings = Settings.from_env()
    except ConfigError as error:
        print(f"configuration error: {error}", file=sys.stderr)
        return 2

    with wiring.open_pool(settings) as pool:
        index = wiring.build_index(pool, settings)
        ingester = Ingester(
            index,
            wiring.build_embedder(settings),
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            signature=f"{settings.embedding_model}/{settings.embedding_dimensions}",
        )
        try:
            report = ingester.sync(
                DirectoryDocumentSource(args.folder), dry_run=args.dry_run, allow_empty=args.allow_empty
            )
        except (EmptySourceError, FileNotFoundError, ValueError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1

    prefix = "would " if args.dry_run else ""
    for label, ids in (("add", report.added), ("update", report.updated), ("remove", report.removed)):
        for id_ in ids:
            print(f"{prefix}{label}: {id_}")
    print(
        f"{len(report.added)} added, {len(report.updated)} updated, "
        f"{len(report.removed)} removed, {len(report.unchanged)} unchanged"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
