from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from prometheus_fastapi_instrumentator import Instrumentator

from asr_system.application.use_cases.get_call_card import GetCallCardUseCase
from asr_system.application.use_cases.list_calls import ListCallsUseCase
from asr_system.config import get_settings
from asr_system.domain.exceptions import CallNotFoundError, DomainError
from asr_system.infrastructure.repositories.json_store import (
    JsonCallScoreRepository,
    JsonUtteranceRepository,
)

logger = logging.getLogger(__name__)

_api_key_header = APIKeyHeader(name="X-API-Token", auto_error=False)


def _verify_token(token: Annotated[str | None, Security(_api_key_header)]) -> None:
    expected = get_settings().online_secrets.api_token
    if not expected:
        return
    if token != expected:
        raise HTTPException(status_code=401, detail="invalid or missing API token")


class _AppState:
    utterances_repo: JsonUtteranceRepository
    scores_repo: JsonCallScoreRepository
    get_call_card: GetCallCardUseCase
    list_calls: ListCallsUseCase


_state = _AppState()


@asynccontextmanager
async def _lifespan(application: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    _state.utterances_repo = JsonUtteranceRepository(settings.storage.output_dir)
    _state.scores_repo = JsonCallScoreRepository(settings.storage.output_dir)
    _state.get_call_card = GetCallCardUseCase(
        utterances_repo=_state.utterances_repo, scores_repo=_state.scores_repo
    )
    _state.list_calls = ListCallsUseCase(scores_repo=_state.scores_repo)
    logger.info("Online service started (output_dir=%s)", settings.storage.output_dir)
    yield


app = FastAPI(
    title="ASR Online Service",
    version="0.1.0",
    description="API for accessing call-center ASR quality scores and utterance cards.",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["X-API-Token"],
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics", tags=["ops"])


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    logger.warning("Domain error: %s", exc)
    if isinstance(exc, CallNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/health", summary="Health check", tags=["ops"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get(
    "/calls",
    summary="List calls filtered by negative index threshold",
    tags=["calls"],
    dependencies=[Depends(_verify_token)],
)
def calls(
    min_negative_index: float = Query(default=0.0, ge=0.0, le=1.0),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
    limit: int = Query(default=50, ge=1, le=500, description="Max items to return"),
) -> dict[str, object]:
    all_items = _state.list_calls.execute(min_negative_index=min_negative_index)
    page = all_items[offset : offset + limit]
    return {"items": page, "total": len(all_items), "offset": offset, "limit": limit}


@app.get(
    "/calls/{call_id}",
    summary="Get call card with utterances and score",
    tags=["calls"],
    dependencies=[Depends(_verify_token)],
)
def call_card(call_id: str) -> dict[str, object]:
    payload = _state.get_call_card.execute(call_id)
    if payload["score"] is None:
        raise CallNotFoundError(call_id)
    return payload
