"""The HTTP interface to the knowledge base.

    POST /answer   {"question": "..."}  ->  {"found": true, "text": "..."}
    GET  /health

Every /answer request needs `Authorization: Bearer <key>`. Question text is never logged:
the logs record only whether an answer was found and how long it took.
"""

import logging
import time
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from kb_service.auth import ApiKeyVerifier
from kb_service.interfaces import Answerer
from kb_service.ratelimit import RateLimiter

logger = logging.getLogger("kb_service.app")


class AnswerResponse(BaseModel):
    found: bool
    text: str


def create_app(
    answerer: Answerer,
    verifier: ApiKeyVerifier,
    limiter: RateLimiter,
    *,
    max_question_chars: int = 500,
    lifespan: Any = None,
) -> FastAPI:
    # The interactive docs are switched off: this endpoint is reachable from the internet.
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    class AnswerRequest(BaseModel):
        question: str = Field(min_length=1, max_length=max_question_chars)

    def require_key(authorization: str | None = Header(default=None)) -> None:
        scheme, _, token = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not verifier.verify(token.strip()):
            raise HTTPException(401, "unauthorized", headers={"WWW-Authenticate": "Bearer"})

    def require_capacity() -> None:
        if not limiter.allow():
            raise HTTPException(429, "too many requests", headers={"Retry-After": str(int(limiter.window_seconds))})

    @app.exception_handler(RequestValidationError)
    def invalid_request(_request: Any, _error: RequestValidationError) -> JSONResponse:
        # The default response echoes the offending input back, which here is a caller's question.
        return JSONResponse({"detail": "invalid request"}, status_code=422)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/answer", response_model=AnswerResponse, dependencies=[Depends(require_key), Depends(require_capacity)])
    def answer(request: AnswerRequest) -> AnswerResponse:
        started = time.monotonic()
        try:
            result = answerer.answer(request.question)
        except Exception as error:
            logger.error("answering failed: %s", type(error).__name__)
            raise HTTPException(503, "temporarily unavailable")
        logger.info("answered found=%s ms=%d", result.found, (time.monotonic() - started) * 1000)
        return AnswerResponse(found=result.found, text=result.text)

    return app
