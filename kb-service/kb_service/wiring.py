"""Builds the real implementations from Settings.

The only module that knows which vendors are behind the interfaces, so swapping the
database or the embedding provider means changing this file and nothing else.
"""

from typing import Any

from psycopg_pool import ConnectionPool

from kb_service.answering import RagAnswerer
from kb_service.embedding import OpenAIEmbedder
from kb_service.generation import OpenAIGenerator
from kb_service.pgvector_index import PgVectorIndex
from kb_service.retrieval import IndexRetriever
from kb_service.settings import Settings


def build_openai_client(settings: Settings, max_retries: int) -> Any:
    from openai import OpenAI

    return OpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds, max_retries=max_retries)


def build_embedder(settings: Settings, client: Any = None) -> OpenAIEmbedder:
    client = client or build_openai_client(settings, max_retries=2)
    return OpenAIEmbedder(client, settings.embedding_model, settings.embedding_dimensions)


def open_pool(settings: Settings) -> ConnectionPool:
    """Use as a context manager (`with open_pool(settings) as pool:`) or call pool.open()."""
    return ConnectionPool(settings.database_url, min_size=1, max_size=4, open=False)


def build_index(pool: ConnectionPool, settings: Settings) -> PgVectorIndex:
    index = PgVectorIndex(pool)
    index.ensure_schema(settings.embedding_dimensions)
    return index


def build_answerer(pool: ConnectionPool, settings: Settings) -> RagAnswerer:
    """A caller is waiting on the phone, so requests made while answering retry only once."""
    client = build_openai_client(settings, max_retries=1)
    retriever = IndexRetriever(build_embedder(settings, client), build_index(pool, settings))
    generator = OpenAIGenerator(client, settings.chat_model, settings.organization_name, settings.answer_max_tokens)
    return RagAnswerer(retriever, generator, settings.retrieval_limit)
