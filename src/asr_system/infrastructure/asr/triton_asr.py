"""ASR adapter that calls a remote NVIDIA Triton Inference Server."""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

import httpx

from asr_system.domain.ports import ASRPort

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(timeout=300.0, connect=10.0)


class TritonAsrAdapter(ASRPort):
    """Sends audio bytes to Triton and parses segment output."""

    def __init__(self, url: str, model: str = "whisper") -> None:
        self._url = url.rstrip("/")
        self._model = model
        self._infer_url = f"{self._url}/v2/models/{self._model}/infer"
        logger.info("TritonASR configured: %s (model=%s)", self._infer_url, model)

    def transcribe(self, audio_path: str) -> list[tuple[float, float, str]]:
        audio_bytes = Path(audio_path).read_bytes()
        encoded = base64.b64encode(audio_bytes).decode("ascii")

        payload = {
            "inputs": [
                {
                    "name": "AUDIO_DATA",
                    "shape": [1],
                    "datatype": "BYTES",
                    "data": [encoded],
                }
            ],
            "outputs": [{"name": "SEGMENTS"}],
        }

        resp = httpx.post(self._infer_url, json=payload, timeout=_TIMEOUT)
        resp.raise_for_status()

        body = resp.json()
        raw = body["outputs"][0]["data"][0]
        segments: list[list[float | str]] = json.loads(raw)

        return [(float(s[0]), float(s[1]), str(s[2])) for s in segments]
