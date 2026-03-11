from fastapi import FastAPI, HTTPException, Query

from asr_system.application.use_cases.get_call_card import GetCallCardUseCase
from asr_system.application.use_cases.list_calls import ListCallsUseCase
from asr_system.config import get_settings
from asr_system.infrastructure.repositories.json_store import (
    JsonCallScoreRepository,
    JsonUtteranceRepository,
)

settings = get_settings()
utterances_repo = JsonUtteranceRepository(settings.storage.output_dir)
scores_repo = JsonCallScoreRepository(settings.storage.output_dir)
get_call_card = GetCallCardUseCase(utterances_repo=utterances_repo, scores_repo=scores_repo)
list_calls = ListCallsUseCase(scores_repo=scores_repo)

app = FastAPI(title="ASR Online Service", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/calls")
def calls(min_negative_index: float = Query(default=0.0, ge=0.0, le=1.0)) -> dict:
    return {"items": list_calls.execute(min_negative_index=min_negative_index)}


@app.get("/calls/{call_id}")
def call_card(call_id: str) -> dict:
    payload = get_call_card.execute(call_id)
    if payload["score"] is None and not payload["utterances"]:
        raise HTTPException(status_code=404, detail="call not found")
    return payload
