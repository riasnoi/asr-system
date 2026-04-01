"""Tests for infrastructure adapters."""

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from asr_system.domain.entities import CallScore, Utterance
from asr_system.domain.value_objects import Emotion
from asr_system.infrastructure.asr.mock_asr import MockAsrAdapter
from asr_system.infrastructure.emotion.rule_based import RuleBasedEmotionAdapter
from asr_system.infrastructure.ingest.local_fs import LocalFsIngest
from asr_system.infrastructure.repositories.json_store import (
    JsonCallScoreRepository,
    JsonUtteranceRepository,
)
from asr_system.infrastructure.speaker.rule_speaker import AlternatingSpeakerAttribution


class TestLocalFsIngest:
    def test_returns_audio_files_for_date(self, tmp_path: Path) -> None:
        day_dir = tmp_path / "2026-03-10"
        day_dir.mkdir()
        (day_dir / "call1.wav").touch()
        (day_dir / "call2.mp3").touch()
        (day_dir / "readme.txt").touch()

        ingest = LocalFsIngest(str(tmp_path))
        paths = ingest.list_audio_paths(date(2026, 3, 10))

        assert len(paths) == 2
        assert all(p.endswith((".wav", ".mp3")) for p in paths)

    def test_returns_empty_for_missing_date(self, tmp_path: Path) -> None:
        ingest = LocalFsIngest(str(tmp_path))
        assert ingest.list_audio_paths(date(2099, 1, 1)) == []


class TestMockAsrAdapter:
    def test_returns_two_segments(self) -> None:
        asr = MockAsrAdapter()
        segments = asr.transcribe("/tmp/test.wav")
        assert len(segments) == 2
        assert all(len(s) == 3 for s in segments)


class TestAlternatingSpeakerAttribution:
    def test_alternates_speakers(self) -> None:
        segments = [(0.0, 1.0, "a"), (1.0, 2.0, "b"), (2.0, 3.0, "c")]
        result = AlternatingSpeakerAttribution().assign_speakers(segments)
        speakers = [r[3] for r in result]
        assert speakers == ["operator", "client", "operator"]


class TestRuleBasedEmotionAdapter:
    @pytest.mark.parametrize(
        "text, expected_emotion",
        [
            ("there is an issue", Emotion.ANGRY),
            ("I feel sad", Emotion.SAD),
            ("thanks a lot", Emotion.POSITIVE),
            ("hello world", Emotion.NEUTRAL),
        ],
    )
    def test_classifies_by_keywords(self, text: str, expected_emotion: Emotion) -> None:
        emotion, confidence = RuleBasedEmotionAdapter().classify(text)
        assert emotion == expected_emotion
        assert 0.0 < confidence <= 1.0


class TestJsonUtteranceRepositoryIdempotency:
    def test_delete_by_call_id_removes_only_target(self, tmp_path: Path) -> None:
        repo = JsonUtteranceRepository(str(tmp_path))
        repo.save_many([
            Utterance("c1", "client", 0, 1, "hi", Emotion.NEUTRAL, 0.8),
            Utterance("c2", "client", 0, 1, "bye", Emotion.NEUTRAL, 0.7),
        ])

        repo.delete_by_call_id("c1")

        assert repo.get_by_call_id("c1") == []
        assert len(repo.get_by_call_id("c2")) == 1

    def test_delete_nonexistent_is_safe(self, tmp_path: Path) -> None:
        repo = JsonUtteranceRepository(str(tmp_path))
        repo.delete_by_call_id("nope")


class TestJsonCallScoreRepository:
    def test_save_upserts_by_call_id(self, tmp_path: Path) -> None:
        repo = JsonCallScoreRepository(str(tmp_path))
        ts = datetime(2026, 1, 1, tzinfo=UTC)

        repo.save(CallScore("c1", 0.1, 0.2, ts))
        repo.save(CallScore("c1", 0.9, 0.8, ts))

        assert len(repo.list_all()) == 1
        assert repo.get("c1").negative_index_client == 0.9
