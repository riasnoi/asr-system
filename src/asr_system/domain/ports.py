from datetime import date
from typing import Protocol, Sequence

from .entities import CallScore, Utterance
from .value_objects import Emotion


class IngestPort(Protocol):
    def list_audio_paths(self, target_date: date) -> Sequence[str]:
        """Return source audio file paths for a specific date."""


class ASRPort(Protocol):
    def transcribe(self, audio_path: str) -> Sequence[tuple[float, float, str]]:
        """Return segments as (start_sec, end_sec, text)."""


class SpeakerAttributionPort(Protocol):
    def assign_speakers(
        self, segments: Sequence[tuple[float, float, str]]
    ) -> Sequence[tuple[float, float, str, str]]:
        """Return segments as (start_sec, end_sec, text, speaker)."""


class EmotionPort(Protocol):
    def classify(self, text: str) -> tuple[Emotion, float]:
        """Return emotion and confidence."""


class UtteranceRepositoryPort(Protocol):
    def save_many(self, utterances: Sequence[Utterance]) -> None:
        ...

    def get_by_call_id(self, call_id: str) -> Sequence[Utterance]:
        ...


class CallScoreRepositoryPort(Protocol):
    def save(self, score: CallScore) -> None:
        ...

    def get(self, call_id: str) -> CallScore | None:
        ...
