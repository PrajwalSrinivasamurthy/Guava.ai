"""Runs against a real Postgres with pgvector. Skipped unless KB_TEST_DATABASE_URL is set.

Each test uses its own throwaway table, never the real one:

    KB_TEST_DATABASE_URL=postgresql://... uv run pytest tests/test_pgvector_index.py
"""

import os
import uuid

import pytest
from psycopg_pool import ConnectionPool

from kb_service.pgvector_index import PgVectorIndex, SchemaMismatch

_URL = os.environ.get("KB_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not _URL, reason="set KB_TEST_DATABASE_URL to run against Postgres")


@pytest.fixture
def index():
    table = f"kb_test_{uuid.uuid4().hex[:12]}"
    with ConnectionPool(_URL, min_size=1, max_size=2, open=False) as pool:
        index = PgVectorIndex(pool, table)
        index.ensure_schema(3)
        yield index
        with pool.connection() as conn:
            conn.execute(f"DROP TABLE IF EXISTS {table}")


def test_ensure_schema_can_run_twice_but_rejects_a_different_vector_size(index):
    index.ensure_schema(3)

    with pytest.raises(SchemaMismatch):
        index.ensure_schema(4)


def test_a_table_name_must_be_a_plain_identifier():
    with pytest.raises(ValueError):
        PgVectorIndex(None, "kb; DROP TABLE users")


def test_replace_document_stores_its_fingerprint_and_passages(index):
    index.replace_document("a.md", "fp1", ["one", "two"], [[1, 0, 0], [0, 1, 0]])

    assert index.fingerprints() == {"a.md": "fp1"}
    assert set(index.search([1, 0, 0], 5)) == {"one", "two"}


def test_replacing_a_document_drops_its_old_passages(index):
    index.replace_document("a.md", "fp1", ["old one", "old two", "old three"], [[1, 0, 0]] * 3)

    index.replace_document("a.md", "fp2", ["new"], [[0, 0, 1]])

    assert index.fingerprints() == {"a.md": "fp2"}
    assert index.search([1, 0, 0], 10) == ["new"]


def test_search_returns_the_closest_passage_first(index):
    index.replace_document("a.md", "f", ["x-axis"], [[1, 0, 0]])
    index.replace_document("b.md", "f", ["y-axis"], [[0, 1, 0]])

    assert index.search([0.9, 0.1, 0], 2) == ["x-axis", "y-axis"]
    assert index.search([0.1, 0.9, 0], 1) == ["y-axis"]


def test_delete_documents_removes_only_those_documents(index):
    index.replace_document("a.md", "f", ["keep"], [[1, 0, 0]])
    index.replace_document("b.md", "f", ["drop"], [[0, 1, 0]])

    index.delete_documents(["b.md"])

    assert index.fingerprints() == {"a.md": "f"}
