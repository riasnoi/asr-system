"""Emotion adapter that calls a remote NVIDIA Triton Inference Server."""

from __future__ import annotations

import logging

import httpx

from asr_system.domain.ports import EmotionPort
from asr_system.domain.value_objects import Emotion

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(timeout=30.0, connect=10.0)

_LABEL_MAP: dict[str, Emotion] = {
    "positive": Emotion.POSITIVE,
    "sad": Emotion.SAD,
    "angry": Emotion.ANGRY,
    "neutral": Emotion.NEUTRAL,
}


class TritonEmotionAdapter(EmotionPort):
    """Sends text to Triton and parses emotion classification output."""

    def __init__(self, url: str, model: str = "rubert_emotion") -> None:
        self._url = url.rstrip("/")
        self._model = model
        self._infer_url = f"{self._url}/v2/models/{self._model}/infer"
        logger.info("TritonEmotion configured: %s (model=%s)", self._infer_url, model)

    def classify(self, text: str) -> tuple[Emotion, float]:
        payload = {
            "inputs": [
                {
                    "name": "TEXT",
                    "shape": [1],
                    "datatype": "BYTES",
                    "data": [text],
                }
            ],
            "outputs": [{"name": "EMOTION"}, {"name": "CONFIDENCE"}],
        }

        resp = httpx.post(self._infer_url, json=payload, timeout=_TIMEOUT)
        resp.raise_for_status()

        body = resp.json()
        outputs = {o["name"]: o["data"] for o in body["outputs"]}
        label = str(outputs["EMOTION"][0]).lower()
        confidence = float(outputs["CONFIDENCE"][0])

        emotion = _LABEL_MAP.get(label, Emotion.NEUTRAL)
        return emotion, confidence
