from __future__ import annotations

import logging
from datetime import date

from asr_system.application.use_cases.batch_process_calls import BatchProcessCallsUseCase
from asr_system.application.use_cases.process_call import ProcessCallUseCase
from asr_system.config import get_settings
from asr_system.infrastructure.factory import (
    create_asr_adapter,
    create_emotion_adapter,
    create_speaker_adapter,
)
from asr_system.infrastructure.ingest.local_fs import LocalFsIngest
from asr_system.infrastructure.repositories.json_store import (
    JsonCallScoreRepository,
    JsonUtteranceRepository,
)

logger = logging.getLogger(__name__)


class BatchRunner:
    def __init__(self) -> None:
        settings = get_settings()
        utterances_repo = JsonUtteranceRepository(settings.storage.output_dir)
        scores_repo = JsonCallScoreRepository(settings.storage.output_dir)
        process_call = ProcessCallUseCase(
            asr=create_asr_adapter(settings),
            speaker_attribution=create_speaker_adapter(settings),
            emotion=create_emotion_adapter(settings),
            utterances_repo=utterances_repo,
            scores_repo=scores_repo,
        )
        self.use_case = BatchProcessCallsUseCase(
            ingest=LocalFsIngest(settings.storage.input_dir),
            process_call=process_call,
        )
        logger.info(
            "BatchRunner initialised (asr=%s, emotion=%s, input=%s, output=%s)",
            settings.asr.provider,
            settings.emotion.provider,
            settings.storage.input_dir,
            settings.storage.output_dir,
        )

    def run(self, target_date: date) -> list[str]:
        return self.use_case.execute(target_date)
