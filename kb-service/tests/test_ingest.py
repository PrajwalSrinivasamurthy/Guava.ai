import pytest
from fakes import FakeEmbedder, InMemoryIndex, StaticSource

from kb_service.domain import KnowledgeDocument
from kb_service.ingest import EmptySourceError, Ingester
from kb_service.retrieval import IndexRetriever

_BOOKS = KnowledgeDocument("books.md", "You need a textbook for each course.")
_FEES = KnowledgeDocument("fees.md", "Tuition is billed each semester.")


def _ingester(index, embedder, **overrides):
    settings = {"chunk_size": 1000, "chunk_overlap": 100, "signature": "model/5"}
    return Ingester(index, embedder, **{**settings, **overrides})


def test_new_documents_are_added_and_become_searchable():
    index, embedder = InMemoryIndex(), FakeEmbedder()

    report = _ingester(index, embedder).sync(StaticSource(_BOOKS, _FEES))

    assert report.added == ["books.md", "fees.md"]
    assert IndexRetriever(embedder, index).search("which textbook?", 1) == [_BOOKS.text]


def test_unchanged_documents_are_not_embedded_again():
    index, embedder = InMemoryIndex(), FakeEmbedder()
    ingester = _ingester(index, embedder)
    ingester.sync(StaticSource(_BOOKS, _FEES))
    embedder.embedded.clear()

    report = ingester.sync(StaticSource(_BOOKS, _FEES))

    assert report.unchanged == ["books.md", "fees.md"]
    assert embedder.embedded == []


def test_a_changed_document_replaces_its_old_content():
    index, embedder = InMemoryIndex(), FakeEmbedder()
    ingester = _ingester(index, embedder)
    ingester.sync(StaticSource(_BOOKS))

    report = ingester.sync(StaticSource(KnowledgeDocument("books.md", "Textbooks are now optional.")))

    assert report.updated == ["books.md"]
    assert index.documents["books.md"][1] == ["Textbooks are now optional."]


def test_documents_missing_from_the_source_are_removed():
    index, embedder = InMemoryIndex(), FakeEmbedder()
    ingester = _ingester(index, embedder)
    ingester.sync(StaticSource(_BOOKS, _FEES))

    report = ingester.sync(StaticSource(_BOOKS))

    assert report.removed == ["fees.md"]
    assert list(index.documents) == ["books.md"]


def test_dry_run_reports_changes_without_making_them():
    index, embedder = InMemoryIndex(), FakeEmbedder()

    report = _ingester(index, embedder).sync(StaticSource(_BOOKS), dry_run=True)

    assert report.added == ["books.md"]
    assert index.documents == {}
    assert embedder.embedded == []


def test_an_empty_source_does_not_wipe_a_populated_index():
    index, embedder = InMemoryIndex(), FakeEmbedder()
    ingester = _ingester(index, embedder)
    ingester.sync(StaticSource(_BOOKS))

    with pytest.raises(EmptySourceError):
        ingester.sync(StaticSource())
    assert "books.md" in index.documents

    assert ingester.sync(StaticSource(), allow_empty=True).removed == ["books.md"]
    assert index.documents == {}


def test_an_empty_source_and_an_empty_index_is_fine():
    assert _ingester(InMemoryIndex(), FakeEmbedder()).sync(StaticSource()).added == []


def test_changing_the_chunking_or_embedding_setup_re_embeds_everything():
    index, embedder = InMemoryIndex(), FakeEmbedder()
    _ingester(index, embedder).sync(StaticSource(_BOOKS))

    assert _ingester(index, embedder, chunk_size=500).sync(StaticSource(_BOOKS)).updated == ["books.md"]
    assert _ingester(index, embedder, chunk_size=500, signature="other/5").sync(StaticSource(_BOOKS)).updated == [
        "books.md"
    ]


def test_duplicate_document_ids_are_rejected():
    with pytest.raises(ValueError, match="books.md"):
        _ingester(InMemoryIndex(), FakeEmbedder()).sync(StaticSource(_BOOKS, _BOOKS))
