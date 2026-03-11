from dataclasses import dataclass
from pathlib import Path

from asr_system.domain.entities import Utterance
from asr_system.domain.ports import (
    ASRPort,
    CallScoreRepositoryPort,
    EmotionPort,
    SpeakerAttributionPort,
    UtteranceRepositoryPort,
)
from asr_system.domain.services import build_call_score


@dataclass
class ProcessCallUseCase:
    asr: ASRPort
    speaker_attribution: SpeakerAttributionPort
    emotion: EmotionPort
    utterances_repo: UtteranceRepositoryPort
    scores_repo: CallScoreRepositoryPort

    def execute(self, audio_path: str) -> str:
        call_id = Path(audio_path).stem
        segments = self.asr.transcribe(audio_path)
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

        self.utterances_repo.save_many(utterances)
        self.scores_repo.save(build_call_score(call_id, utterances))
        return call_id
