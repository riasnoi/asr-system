from __future__ import annotations

import asyncio
import logging
import re
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, Security, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from prometheus_fastapi_instrumentator import Instrumentator

from asr_system.application.use_cases.get_call_card import GetCallCardUseCase
from asr_system.application.use_cases.list_calls import ListCallsUseCase
from asr_system.application.use_cases.process_call import ProcessCallUseCase
from asr_system.config import get_settings
from asr_system.domain.exceptions import CallNotFoundError, DomainError
from asr_system.infrastructure.factory import (
    create_asr_adapter,
    create_emotion_adapter,
    create_repository_adapters,
    create_speaker_adapter,
)

logger = logging.getLogger(__name__)

_api_key_header = APIKeyHeader(name="X-API-Token", auto_error=False)

_SAFE_ID = re.compile(r"[^\w\-.]")


def _verify_token(token: Annotated[str | None, Security(_api_key_header)]) -> None:
    expected = get_settings().online_secrets.api_token
    if not expected:
        return
    if token != expected:
        raise HTTPException(status_code=401, detail="invalid or missing API token")


class _AppState:
    get_call_card: GetCallCardUseCase
    list_calls: ListCallsUseCase
    process_call: ProcessCallUseCase


_state = _AppState()


@asynccontextmanager
async def _lifespan(_application: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    utterances_repo, scores_repo = create_repository_adapters(settings)
    _state.get_call_card = GetCallCardUseCase(
        utterances_repo=utterances_repo, scores_repo=scores_repo
    )
    _state.list_calls = ListCallsUseCase(scores_repo=scores_repo)
    _state.process_call = ProcessCallUseCase(
        asr=create_asr_adapter(settings),
        speaker_attribution=create_speaker_adapter(settings),
        emotion=create_emotion_adapter(settings),
        utterances_repo=utterances_repo,
        scores_repo=scores_repo,
    )
    repo_backend = "postgresql" if settings.db.dsn.startswith("postgresql") else "json"
    logger.info(
        "Online service started (repo=%s, asr=%s, emotion=%s)",
        repo_backend,
        settings.asr.provider,
        settings.emotion.provider,
    )
    yield


app = FastAPI(
    title="ASR Online Service",
    version="0.2.0",
    description="Real-time transcription and call-center ASR quality scores.",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Token", "Content-Type"],
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics", tags=["ops"])


@app.exception_handler(DomainError)
async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
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


@app.post(
    "/transcribe",
    summary="Transcribe an audio file in real time and store the result",
    tags=["calls"],
    dependencies=[Depends(_verify_token)],
)
async def transcribe(
    file: UploadFile = File(..., description="Audio file (wav / mp3 / flac)"),
    call_id: str | None = Form(
        default=None,
        description="Optional call ID; defaults to the uploaded filename stem",
    ),
) -> dict[str, object]:
    """Upload an audio file, transcribe it via Triton, classify emotions,
    persist the result in the shared database and return the full call card."""
    original_name = file.filename or "audio.wav"
    suffix = Path(original_name).suffix or ".wav"
    stem = call_id or Path(original_name).stem
    stem = _SAFE_ID.sub("_", stem)[:128]

    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")

    with tempfile.TemporaryDirectory() as tmp_dir:
        audio_path = Path(tmp_dir) / f"{stem}{suffix}"
        audio_path.write_bytes(content)

        loop = asyncio.get_event_loop()
        try:
            processed_id: str = await loop.run_in_executor(
                None, _state.process_call.execute, str(audio_path)
            )
        except Exception as exc:
            logger.exception("Transcription failed for call_id=%s", stem)
            raise HTTPException(status_code=500, detail=f"Transcription error: {exc}") from exc

    return _state.get_call_card.execute(processed_id)
