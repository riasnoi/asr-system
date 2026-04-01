"""Tests for Triton remote adapters."""

from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest

from asr_system.domain.value_objects import Emotion
from asr_system.infrastructure.asr.triton_asr import TritonAsrAdapter
from asr_system.infrastructure.emotion.triton_emotion import TritonEmotionAdapter


def _mock_response(json_body: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code=status_code, json=json_body)


class TestTritonAsrAdapter:
    def test_transcribe_parses_segments(self, tmp_path) -> None:
        audio_file = tmp_path / "call.wav"
        audio_file.write_bytes(b"fake-audio-data")

        segments = [[0.0, 2.5, "hello world"], [2.5, 5.0, "goodbye"]]
        triton_response = {"outputs": [{"name": "SEGMENTS", "data": [json.dumps(segments)]}]}

        adapter = TritonAsrAdapter(url="http://triton:8000", model="whisper")
        with patch("asr_system.infrastructure.asr.triton_asr.httpx.post") as mock_post:
            mock_post.return_value = _mock_response(triton_response)
            result = adapter.transcribe(str(audio_file))

        assert len(result) == 2
        assert result[0] == (0.0, 2.5, "hello world")
        assert result[1] == (2.5, 5.0, "goodbye")

        call_payload = mock_post.call_args[1]["json"]
        assert call_payload["inputs"][0]["name"] == "AUDIO_DATA"
        assert call_payload["inputs"][0]["datatype"] == "BYTES"

    def test_transcribe_raises_on_http_error(self, tmp_path) -> None:
        audio_file = tmp_path / "call.wav"
        audio_file.write_bytes(b"data")

        adapter = TritonAsrAdapter(url="http://triton:8000", model="whisper")
        with patch("asr_system.infrastructure.asr.triton_asr.httpx.post") as mock_post:
            mock_post.return_value = httpx.Response(status_code=500, text="Internal error")
            with pytest.raises(httpx.HTTPStatusError):
                adapter.transcribe(str(audio_file))


class TestTritonEmotionAdapter:
    @pytest.mark.parametrize(
        "label, expected",
        [
            ("angry", Emotion.ANGRY),
            ("sad", Emotion.SAD),
            ("positive", Emotion.POSITIVE),
            ("neutral", Emotion.NEUTRAL),
            ("ANGRY", Emotion.ANGRY),
            ("unknown_label", Emotion.NEUTRAL),
        ],
    )
    def test_classify_maps_labels(self, label: str, expected: Emotion) -> None:
        triton_response = {
            "outputs": [
                {"name": "EMOTION", "data": [label]},
                {"name": "CONFIDENCE", "data": [0.85]},
            ]
        }

        adapter = TritonEmotionAdapter(url="http://triton:8000", model="rubert_emotion")
        with patch("asr_system.infrastructure.emotion.triton_emotion.httpx.post") as mock_post:
            mock_post.return_value = _mock_response(triton_response)
            emotion, confidence = adapter.classify("some text")

        assert emotion == expected
        assert confidence == 0.85

    def test_classify_sends_correct_payload(self) -> None:
        triton_response = {
            "outputs": [
                {"name": "EMOTION", "data": ["neutral"]},
                {"name": "CONFIDENCE", "data": [0.6]},
            ]
        }

        adapter = TritonEmotionAdapter(url="http://triton:8000", model="rubert_emotion")
        with patch("asr_system.infrastructure.emotion.triton_emotion.httpx.post") as mock_post:
            mock_post.return_value = _mock_response(triton_response)
            adapter.classify("hello world")

        call_payload = mock_post.call_args[1]["json"]
        assert call_payload["inputs"][0]["name"] == "TEXT"
        assert call_payload["inputs"][0]["data"] == ["hello world"]
        assert call_payload["outputs"] == [{"name": "EMOTION"}, {"name": "CONFIDENCE"}]

    def test_classify_raises_on_http_error(self) -> None:
        adapter = TritonEmotionAdapter(url="http://triton:8000", model="rubert_emotion")
        with patch("asr_system.infrastructure.emotion.triton_emotion.httpx.post") as mock_post:
            mock_post.return_value = httpx.Response(status_code=503, text="Unavailable")
            with pytest.raises(httpx.HTTPStatusError):
                adapter.classify("test")
