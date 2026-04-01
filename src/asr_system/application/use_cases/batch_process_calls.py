from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from asr_system.application.use_cases.process_call import ProcessCallUseCase
from asr_system.domain.ports import IngestPort

logger = logging.getLogger(__name__)


@dataclass
class BatchProcessCallsUseCase:
    ingest: IngestPort
    process_call: ProcessCallUseCase

    def execute(self, target_date: date) -> list[str]:
        paths = self.ingest.list_audio_paths(target_date)
        logger.info("Batch run for %s: %d audio files found", target_date.isoformat(), len(paths))

        processed_call_ids: list[str] = []
        for path in paths:
            try:
                processed_call_ids.append(self.process_call.execute(path))
            except Exception:  # pylint: disable=broad-exception-caught
                logger.exception("Failed to process %s, skipping", path)
        logger.info("Batch complete: %d/%d calls processed", len(processed_call_ids), len(paths))
        return processed_call_ids
