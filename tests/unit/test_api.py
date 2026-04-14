"""Integration tests for the FastAPI online service."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from asr_system.domain.entities import CallScore, Utterance
from asr_system.domain.value_objects import Emotion
from asr_system.interfaces.online.api import _state, app


class _StubProcessCallUseCase:
    def execute(self, audio_path: str) -> str:
        return Path(audio_path).stem


@pytest.fixture(autouse=True)
def _setup_state(tmp_path):
    from asr_system.application.use_cases.get_call_card import GetCallCardUseCase
    from asr_system.application.use_cases.list_calls import ListCallsUseCase
    from asr_system.infrastructure.repositories.json_store import (
        JsonCallScoreRepository,
        JsonUtteranceRepository,
    )

    _state.utterances_repo = JsonUtteranceRepository(str(tmp_path))
    _state.scores_repo = JsonCallScoreRepository(str(tmp_path))
    _state.get_call_card = GetCallCardUseCase(
        utterances_repo=_state.utterances_repo, scores_repo=_state.scores_repo
    )
    _state.list_calls = ListCallsUseCase(scores_repo=_state.scores_repo)
    _state.process_call = _StubProcessCallUseCase()


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


def _seed_call(call_id: str = "c1", neg_client: float = 0.5, neg_operator: float = 0.3) -> None:
    _state.utterances_repo.save_many(
        [Utterance(call_id, "client", 0, 1, "hi", Emotion.NEUTRAL, 0.8)]
    )
    _state.scores_repo.save(
        CallScore(
            call_id=call_id,
            negative_index_client=neg_client,
            negative_index_operator=neg_operator,
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )


def test_health(client) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_calls_empty(client) -> None:
    resp = client.get("/api/v1/call-summaries")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_calls_with_data(client) -> None:
    _seed_call("c1", 0.5, 0.3)
    _seed_call("c2", 0.9, 0.1)

    resp = client.get("/api/v1/call-summaries?min_negative_index=0.0")
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


def test_calls_pagination(client) -> None:
    for i in range(5):
        _seed_call(f"call-{i}", 0.5, 0.5)

    resp = client.get("/api/v1/call-summaries?offset=2&limit=2")
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["offset"] == 2


def test_call_card_found(client) -> None:
    _seed_call("c1")
    resp = client.get("/api/v1/call-cards/c1")
    assert resp.status_code == 200
    assert resp.json()["call_id"] == "c1"
    assert resp.json()["score"] is not None


def test_call_card_not_found(client) -> None:
    resp = client.get("/api/v1/call-cards/nonexistent")
    assert resp.status_code == 404


def test_transcriptions_create_processed_call(client) -> None:
    resp = client.post(
        "/api/v1/transcriptions",
        files={"file": ("sample.wav", b"fake-audio", "audio/wav")},
        data={"call_id": "demo-call"},
    )

    assert resp.status_code == 201
    assert resp.json()["call_id"] == "demo-call"
    assert resp.headers["Location"].endswith("/api/v1/call-cards/demo-call")
    assert resp.json()["location"].endswith("/api/v1/call-cards/demo-call")


def test_legacy_routes_still_work(client) -> None:
    _seed_call("legacy-call")

    assert client.get("/calls").status_code == 200
    assert client.get("/calls/legacy-call").status_code == 200


def test_auth_required_when_token_set(client, monkeypatch) -> None:
    monkeypatch.setenv("ONLINE_API_TOKEN", "secret-tok")
    from asr_system.config import get_settings

    get_settings.cache_clear()

    resp = client.get("/api/v1/call-summaries")
    assert resp.status_code == 401

    resp = client.get("/api/v1/call-summaries", headers={"X-API-Token": "secret-tok"})
    assert resp.status_code == 200

    monkeypatch.delenv("ONLINE_API_TOKEN", raising=False)
    get_settings.cache_clear()
