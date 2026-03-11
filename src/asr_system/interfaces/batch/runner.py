from datetime import date

from asr_system.application.use_cases.batch_process_calls import BatchProcessCallsUseCase
from asr_system.application.use_cases.process_call import ProcessCallUseCase
from asr_system.config import get_settings
from asr_system.infrastructure.asr.mock_asr import MockAsrAdapter
from asr_system.infrastructure.emotion.rule_based import RuleBasedEmotionAdapter
from asr_system.infrastructure.ingest.local_fs import LocalFsIngest
from asr_system.infrastructure.repositories.json_store import (
    JsonCallScoreRepository,
    JsonUtteranceRepository,
)
from asr_system.infrastructure.speaker.rule_speaker import AlternatingSpeakerAttribution


class BatchRunner:
    def __init__(self) -> None:
        settings = get_settings()
        utterances_repo = JsonUtteranceRepository(settings.storage.output_dir)
        scores_repo = JsonCallScoreRepository(settings.storage.output_dir)
        process_call = ProcessCallUseCase(
            asr=MockAsrAdapter(),
            speaker_attribution=AlternatingSpeakerAttribution(),
            emotion=RuleBasedEmotionAdapter(),
            utterances_repo=utterances_repo,
            scores_repo=scores_repo,
        )
        self.use_case = BatchProcessCallsUseCase(
            ingest=LocalFsIngest(settings.storage.input_dir),
            process_call=process_call,
        )

    def run(self, target_date: date) -> list[str]:
        return self.use_case.execute(target_date)
