"""Builds the real implementations from Settings.

The only module that knows which vendors are behind the interfaces, so swapping the
database or the embedding provider means changing this file and nothing else.
"""

from psycopg_pool import ConnectionPool

from kb_service.embedding import OpenAIEmbedder
from kb_service.pgvector_index import PgVectorIndex
from kb_service.settings import Settings


def build_embedder(settings: Settings) -> OpenAIEmbedder:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds, max_retries=2)
    return OpenAIEmbedder(client, settings.embedding_model, settings.embedding_dimensions)


def open_pool(settings: Settings) -> ConnectionPool:
    """Use as a context manager: `with open_pool(settings) as pool:`."""
    return ConnectionPool(settings.database_url, min_size=1, max_size=4, open=False)


def build_index(pool: ConnectionPool, settings: Settings) -> PgVectorIndex:
    index = PgVectorIndex(pool)
    index.ensure_schema(settings.embedding_dimensions)
    return index
