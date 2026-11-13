"""VectorIndex backed by Postgres with the pgvector extension.

One row per passage, keyed by (document_id, chunk_no), with the fingerprint of the
document it came from. Replacing or deleting a document is a single transaction, so a
crash mid-ingest never leaves a half-updated document behind.
"""

import re

from psycopg_pool import ConnectionPool

_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


class SchemaMismatch(Exception):
    """The table already exists with a different vector size than is configured."""


class PgVectorIndex:
    def __init__(self, pool: ConnectionPool, table: str = "kb_chunks"):
        if not _IDENTIFIER.match(table):
            raise ValueError(f"invalid table name {table!r}")
        self._pool = pool
        self._table = table

    def ensure_schema(self, dimensions: int) -> None:
        table = self._table
        with self._pool.connection() as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS {table} ("
                "document_id text NOT NULL, "
                "chunk_no integer NOT NULL, "
                "content text NOT NULL, "
                "fingerprint text NOT NULL, "
                f"embedding vector({int(dimensions)}) NOT NULL, "
                "PRIMARY KEY (document_id, chunk_no))"
            )
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS {table}_embedding_idx "
                f"ON {table} USING hnsw (embedding vector_cosine_ops)"
            )
            stored = conn.execute(
                "SELECT atttypmod FROM pg_attribute WHERE attrelid = to_regclass(%s) AND attname = 'embedding'",
                (table,),
            ).fetchone()[0]
        if stored != dimensions:
            raise SchemaMismatch(
                f"table {table} stores {stored}-dimension vectors but {dimensions} is configured; "
                "use a new table or re-ingest into an empty one"
            )

    def fingerprints(self) -> dict[str, str]:
        with self._pool.connection() as conn:
            rows = conn.execute(
                f"SELECT document_id, min(fingerprint) FROM {self._table} GROUP BY document_id"
            ).fetchall()
        return dict(rows)

    def replace_document(
        self, document_id: str, fingerprint: str, chunks: list[str], vectors: list[list[float]]
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must be the same length")
        rows = [
            (document_id, number, chunk, fingerprint, _literal(vector))
            for number, (chunk, vector) in enumerate(zip(chunks, vectors))
        ]
        with self._pool.connection() as conn:
            conn.execute(f"DELETE FROM {self._table} WHERE document_id = %s", (document_id,))
            with conn.cursor() as cursor:
                cursor.executemany(
                    f"INSERT INTO {self._table} (document_id, chunk_no, content, fingerprint, embedding) "
                    "VALUES (%s, %s, %s, %s, %s::vector)",
                    rows,
                )

    def delete_documents(self, document_ids: list[str]) -> None:
        with self._pool.connection() as conn:
            conn.execute(f"DELETE FROM {self._table} WHERE document_id = ANY(%s)", (document_ids,))

    def search(self, vector: list[float], limit: int) -> list[str]:
        with self._pool.connection() as conn:
            rows = conn.execute(
                f"SELECT content FROM {self._table} ORDER BY embedding <=> %s::vector LIMIT %s",
                (_literal(vector), limit),
            ).fetchall()
        return [content for (content,) in rows]


def _literal(vector: list[float]) -> str:
    return "[" + ",".join(repr(float(value)) for value in vector) + "]"
