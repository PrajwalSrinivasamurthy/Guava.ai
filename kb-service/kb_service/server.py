"""Entry point for the running service:

    uvicorn --factory kb_service.server:create --host 0.0.0.0 --port 8120
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from kb_service import wiring
from kb_service.app import create_app
from kb_service.auth import ApiKeyVerifier
from kb_service.ratelimit import RateLimiter
from kb_service.settings import ConfigError, Settings


def create() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings.from_env()
    if not settings.api_key_hashes:
        raise ConfigError("KB_API_KEY_HASHES is not set; the service would accept no requests")

    pool = wiring.open_pool(settings)
    pool.open(wait=True, timeout=15)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        pool.close()

    return create_app(
        wiring.build_answerer(pool, settings),
        ApiKeyVerifier(settings.api_key_hashes),
        RateLimiter(settings.rate_limit_per_minute),
        max_question_chars=settings.max_question_chars,
        lifespan=lifespan,
    )
