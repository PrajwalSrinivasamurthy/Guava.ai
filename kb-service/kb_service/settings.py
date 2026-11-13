"""Runtime configuration, read from environment variables.

Settings.from_env() validates everything up front and reports every problem in a single
ConfigError, so a misconfigured deploy fails at startup with the full list instead of
one missing variable at a time. Secrets are excluded from repr() so they can't leak
into a log line or traceback.

The numeric defaults are starting points to be tuned against real questions.
"""

import os
from dataclasses import dataclass, field
from typing import Callable, Mapping


_MAX_INDEXED_DIMENSIONS = 2000


class ConfigError(Exception):
    """One or more environment variables are missing or invalid."""


@dataclass(frozen=True)
class Settings:
    openai_api_key: str = field(repr=False)
    database_url: str = field(repr=False)
    chat_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    chunk_size: int = 1200
    chunk_overlap: int = 150
    retrieval_limit: int = 4
    openai_timeout_seconds: float = 8.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "Settings":
        problems: list[str] = []

        def text(name: str, default: str | None = None) -> str:
            value = env.get(name, "").strip()
            if value:
                return value
            if default is None:
                problems.append(f"{name} is not set")
                return ""
            return default

        def number(name: str, default: float, cast: Callable[[str], float]) -> float:
            raw = env.get(name, "").strip()
            if not raw:
                return default
            try:
                value = cast(raw)
            except ValueError:
                problems.append(f"{name} must be a number, got {raw!r}")
                return default
            if value <= 0:
                problems.append(f"{name} must be greater than zero, got {raw!r}")
                return default
            return value

        settings = cls(
            openai_api_key=text("OPENAI_API_KEY"),
            database_url=text("DATABASE_URL"),
            chat_model=text("OPENAI_CHAT_MODEL", cls.chat_model),
            embedding_model=text("OPENAI_EMBEDDING_MODEL", cls.embedding_model),
            embedding_dimensions=int(number("OPENAI_EMBEDDING_DIMENSIONS", cls.embedding_dimensions, int)),
            chunk_size=int(number("KB_CHUNK_SIZE", cls.chunk_size, int)),
            chunk_overlap=int(number("KB_CHUNK_OVERLAP", cls.chunk_overlap, int)),
            retrieval_limit=int(number("KB_RETRIEVAL_LIMIT", cls.retrieval_limit, int)),
            openai_timeout_seconds=number("OPENAI_TIMEOUT_SECONDS", cls.openai_timeout_seconds, float),
        )

        if settings.chunk_overlap >= settings.chunk_size:
            problems.append("KB_CHUNK_OVERLAP must be smaller than KB_CHUNK_SIZE")
        if settings.embedding_dimensions > _MAX_INDEXED_DIMENSIONS:
            problems.append(
                f"OPENAI_EMBEDDING_DIMENSIONS must be at most {_MAX_INDEXED_DIMENSIONS} "
                "(the limit of pgvector's HNSW index)"
            )

        if problems:
            raise ConfigError("; ".join(problems))
        return settings
