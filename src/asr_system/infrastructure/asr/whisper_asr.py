"""Whisper ASR adapter. Requires `openai-whisper` or `faster-whisper` to be installed."""

from __future__ import annotations

import logging

from asr_system.domain.ports import ASRPort

logger = logging.getLogger(__name__)


class WhisperAsrAdapter(ASRPort):
    def __init__(self, model_name: str = "whisper-large-v3-turbo") -> None:
        self.model_name = model_name
        logger.info("Loading Whisper model: %s", model_name)
        # TODO: integrate real whisper model loading
        raise ImportError(
            f"Whisper model {model_name!r} integration not yet implemented. "
            "Install openai-whisper and implement model loading here."
        )

    def transcribe(self, audio_path: str) -> list[tuple[float, float, str]]:
        raise NotImplementedError
