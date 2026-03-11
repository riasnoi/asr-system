from dataclasses import dataclass
from datetime import date

from asr_system.application.use_cases.process_call import ProcessCallUseCase
from asr_system.domain.ports import IngestPort


@dataclass
class BatchProcessCallsUseCase:
    ingest: IngestPort
    process_call: ProcessCallUseCase

    def execute(self, target_date: date) -> list[str]:
        processed_call_ids: list[str] = []
        for path in self.ingest.list_audio_paths(target_date):
            processed_call_ids.append(self.process_call.execute(path))
        return processed_call_ids
