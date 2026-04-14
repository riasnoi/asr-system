from __future__ import annotations

import asyncio
import logging
import re
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib import import_module
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, File, Form, HTTPException
from fastapi import Path as PathParam
from fastapi import Query, Request, Security, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

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

_TEMPLATES_DIR = Path(__file__).parent / "templates"

logger = logging.getLogger(__name__)

_api_key_header = APIKeyHeader(name="X-API-Token", auto_error=False)

_SAFE_ID = re.compile(r"[^\w\-.]")
_API_PREFIX = "/api/v1"
_CALL_SUMMARIES_PATH = f"{_API_PREFIX}/call-summaries"
_CALL_CARD_PATH = f"{_API_PREFIX}/call-cards/{{call_id}}"
_TRANSCRIPTIONS_PATH = f"{_API_PREFIX}/transcriptions"
_OPENAPI_TAGS = [
    {
        "name": "calls",
        "description": "Read-only access to processed call summaries and full call cards.",
    },
    {
        "name": "analysis",
        "description": "Submit new audio files for transcription and QA scoring.",
    },
    {
        "name": "ops",
        "description": "Operational endpoints for service health and observability.",
    },
]


class ErrorResponse(BaseModel):
    detail: str = Field(description="Human-readable error message.")


class HealthResponse(BaseModel):
    status: str = Field(description="Service health status.", examples=["ok"])


class CallScoreResponse(BaseModel):
    call_id: str = Field(description="Call identifier.")
    negative_index_client: float = Field(
        description="Client negativity score in the range from 0.0 to 1.0."
    )
    negative_index_operator: float = Field(
        description="Operator negativity score in the range from 0.0 to 1.0."
    )
    updated_at: str = Field(description="Last score update timestamp in ISO 8601 format.")
    overall_score: float = Field(description="Composite QA score in the range from 0 to 100.")
    client_satisfaction: float = Field(description="Client satisfaction score from 0 to 100.")
    operator_quality: float = Field(description="Operator quality score from 0 to 100.")
    talk_ratio_operator: float = Field(
        description="Operator speech share in the range from 0.0 to 1.0."
    )
    total_duration_seconds: float = Field(description="Total call duration in seconds.")


class UtteranceResponse(BaseModel):
    call_id: str = Field(description="Call identifier.")
    speaker: str = Field(description="Utterance speaker label, for example `client` or `operator`.")
    start_sec: float = Field(description="Utterance start timestamp in seconds.")
    end_sec: float = Field(description="Utterance end timestamp in seconds.")
    text: str = Field(description="Recognized utterance text.")
    emotion: str = Field(description="Detected utterance emotion label.")
    confidence: float = Field(description="Emotion classification confidence from 0.0 to 1.0.")


class CallCardResponse(BaseModel):
    call_id: str = Field(description="Call identifier.")
    utterances: list[UtteranceResponse] = Field(description="Transcribed utterances for the call.")
    score: CallScoreResponse | None = Field(description="Aggregated QA score for the call.")


class CallSummariesResponse(BaseModel):
    items: list[CallScoreResponse] = Field(
        description="Paginated list of processed call summaries."
    )
    total: int = Field(description="Total number of matching call summaries before pagination.")
    offset: int = Field(description="Applied pagination offset.")
    limit: int = Field(description="Applied pagination limit.")


class TranscriptionCreatedResponse(BaseModel):
    call_id: str = Field(description="Identifier of the processed call.")
    location: str = Field(description="Absolute URL of the created call card resource.")


def _load_prometheus_instrumentator() -> Any | None:
    try:
        module = import_module("prometheus_fastapi_instrumentator")
    except ModuleNotFoundError:  # pragma: no cover - optional in lightweight dev/test envs
        return None
    return module.Instrumentator


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
    description=(
        "HTTP API for uploading call audio, browsing processed calls, and fetching "
        "full QA call cards with utterances and aggregated scores."
    ),
    lifespan=_lifespan,
    openapi_tags=_OPENAPI_TAGS,
    swagger_ui_parameters={"displayRequestDuration": True, "docExpansion": "list"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Token", "Content-Type"],
)

instrumentator_class = _load_prometheus_instrumentator()

if instrumentator_class is not None:
    instrumentator_class().instrument(app).expose(app, endpoint="/metrics", tags=["ops"])
else:
    logger.warning("Prometheus instrumentator is not installed; /metrics endpoint is disabled")


@app.exception_handler(DomainError)
async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    logger.warning("Domain error: %s", exc)
    if isinstance(exc, CallNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def frontend() -> HTMLResponse:
    return HTMLResponse((_TEMPLATES_DIR / "index.html").read_text(encoding="utf-8"))


@app.get(
    "/health",
    summary="Service health check",
    description="Lightweight probe used by orchestration and monitoring systems.",
    tags=["ops"],
    operation_id="getHealthStatus",
    response_model=HealthResponse,
)
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get(
    _CALL_SUMMARIES_PATH,
    summary="List processed call summaries",
    description=(
        "Returns aggregated QA metrics for processed calls. "
        "Supports filtering by minimum negative index and offset/limit pagination."
    ),
    tags=["calls"],
    dependencies=[Depends(_verify_token)],
    operation_id="listCallSummaries",
    response_model=CallSummariesResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid API token."},
    },
)
@app.get(
    "/calls",
    include_in_schema=False,
    dependencies=[Depends(_verify_token)],
)
def list_call_summaries(
    min_negative_index: float = Query(
        default=0.0,
        ge=0.0,
        le=1.0,
        description=(
            "Return only calls whose client or operator negative index " "is at least this value."
        ),
    ),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
    limit: int = Query(default=50, ge=1, le=500, description="Max items to return"),
) -> dict[str, object]:
    all_items = _state.list_calls.execute(min_negative_index=min_negative_index)
    page = all_items[offset : offset + limit]
    return {"items": page, "total": len(all_items), "offset": offset, "limit": limit}


@app.get(
    _CALL_CARD_PATH,
    summary="Get a full call card",
    description="Returns utterances and aggregated QA scores for one processed call.",
    tags=["calls"],
    dependencies=[Depends(_verify_token)],
    name="get_call_card",
    operation_id="getCallCard",
    response_model=CallCardResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid API token."},
        404: {"model": ErrorResponse, "description": "Call was not found."},
    },
)
@app.get(
    "/calls/{call_id}",
    include_in_schema=False,
    dependencies=[Depends(_verify_token)],
    name="get_call_card_legacy",
)
def call_card(
    call_id: str = PathParam(description="Processed call identifier."),
) -> dict[str, object]:
    payload = _state.get_call_card.execute(call_id)
    if payload["score"] is None:
        raise CallNotFoundError(call_id)
    return payload


@app.post(
    _TRANSCRIPTIONS_PATH,
    summary="Upload audio for transcription and QA scoring",
    description=(
        "Accepts an audio file, runs transcription and post-processing, persists the "
        "result, and returns the location of the created call card."
    ),
    status_code=201,
    tags=["analysis"],
    dependencies=[Depends(_verify_token)],
    name="create_transcription",
    operation_id="createTranscription",
    response_model=TranscriptionCreatedResponse,
    responses={
        201: {
            "description": "Audio file processed successfully. Call card resource created.",
        },
        401: {"model": ErrorResponse, "description": "Missing or invalid API token."},
        422: {"model": ErrorResponse, "description": "Uploaded payload is invalid."},
        500: {"model": ErrorResponse, "description": "Audio processing failed."},
    },
)
@app.post(
    "/calls",
    include_in_schema=False,
    status_code=201,
    dependencies=[Depends(_verify_token)],
    name="create_call_legacy",
)
async def create_call(
    request: Request,
    file: UploadFile = File(
        ...,
        description="Audio file to process. Supported formats depend on the ASR backend.",
    ),
    call_id: str | None = Form(
        default=None,
        description="Optional call identifier. Defaults to the uploaded filename stem.",
    ),
) -> Response:
    """Upload an audio file, transcribe it, classify emotions and persist the
    result. Returns **201 Created** with a ``Location`` header pointing to the
    call card resource and a minimal JSON body so clients can follow up without
    an extra round-trip."""
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

    location = str(request.url_for("get_call_card", call_id=processed_id))
    body = JSONResponse(
        content={"call_id": processed_id, "location": location},
        status_code=201,
        headers={"Location": location},
    )
    return body
