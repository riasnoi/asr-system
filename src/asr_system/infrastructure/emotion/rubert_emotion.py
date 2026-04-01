"""ruBERT emotion adapter. Requires `transformers` and `torch` to be installed."""

from __future__ import annotations

import logging

from asr_system.domain.ports import EmotionPort
from asr_system.domain.value_objects import Emotion

logger = logging.getLogger(__name__)


class RuBertEmotionAdapter(EmotionPort):
    def __init__(self, model_name: str = "cointegrated/rubert-tiny2") -> None:
        self.model_name = model_name
        logger.info("Loading ruBERT emotion model: %s", model_name)
        # TODO: integrate real transformer model loading
        raise ImportError(
            f"ruBERT model {model_name!r} integration not yet implemented. "
            "Install transformers + torch and implement model loading here."
        )

    def classify(self, text: str) -> tuple[Emotion, float]:
        raise NotImplementedError
