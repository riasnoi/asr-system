from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from asr_system.domain.entities import Utterance
from asr_system.domain.exceptions import TranscriptionError
from asr_system.domain.ports import (
    ASRPort,
    CallScoreRepositoryPort,
    EmotionPort,
    SpeakerAttributionPort,
    UtteranceRepositoryPort,
)
from asr_system.domain.services import build_call_score

logger = logging.getLogger(__name__)


@dataclass
class ProcessCallUseCase:
    asr: ASRPort
    speaker_attribution: SpeakerAttributionPort
    emotion: EmotionPort
    utterances_repo: UtteranceRepositoryPort
    scores_repo: CallScoreRepositoryPort

    def execute(self, audio_path: str) -> str:
        call_id = Path(audio_path).stem
        logger.info("Processing call %s from %s", call_id, audio_path)

        try:
            segments = self.asr.transcribe(audio_path)
        except Exception as exc:
            raise TranscriptionError(audio_path, str(exc)) from exc

        enriched = self.speaker_attribution.assign_speakers(segments)

        utterances: list[Utterance] = []
        for start_sec, end_sec, text, speaker in enriched:
            emotion, confidence = self.emotion.classify(text)
            utterances.append(
                Utterance(
                    call_id=call_id,
                    speaker=speaker,
                    start_sec=start_sec,
                    end_sec=end_sec,
                    text=text,
                    emotion=emotion,
                    confidence=confidence,
                )
            )

        self.utterances_repo.delete_by_call_id(call_id)
        self.utterances_repo.save_many(utterances)
        self.scores_repo.save(build_call_score(call_id, utterances))
        logger.info("Call %s processed: %d utterances", call_id, len(utterances))
        return call_id
