from __future__ import annotations

import logging
from datetime import date

from asr_system.application.use_cases.batch_process_calls import BatchProcessCallsUseCase
from asr_system.application.use_cases.process_call import ProcessCallUseCase
from asr_system.config import get_settings
from asr_system.infrastructure.factory import (
    create_asr_adapter,
    create_emotion_adapter,
    create_ingest_adapter,
    create_repository_adapters,
    create_speaker_adapter,
)

logger = logging.getLogger(__name__)


class BatchRunner:
    def __init__(self) -> None:
        settings = get_settings()
        utterances_repo, scores_repo = create_repository_adapters(settings)
        process_call = ProcessCallUseCase(
            asr=create_asr_adapter(settings),
            speaker_attribution=create_speaker_adapter(settings),
            emotion=create_emotion_adapter(settings),
            utterances_repo=utterances_repo,
            scores_repo=scores_repo,
        )
        self.use_case = BatchProcessCallsUseCase(
            ingest=create_ingest_adapter(settings),
            process_call=process_call,
        )
        logger.info(
            "BatchRunner initialised (asr=%s, emotion=%s, ingest=%s, repo=%s)",
            settings.asr.provider,
            settings.emotion.provider,
            "s3" if settings.s3.bucket else "local",
            "postgresql" if settings.db.dsn.startswith("postgresql") else "json",
        )

    def run(self, target_date: date) -> list[str]:
        return self.use_case.execute(target_date)
