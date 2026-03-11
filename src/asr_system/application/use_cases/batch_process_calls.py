from dataclasses import dataclass
from datetime import date

from asr_system.domain.ports import IngestPort


@dataclass
class BatchProcessCallsUseCase:
    ingest: IngestPort

    def execute(self, target_date: date) -> list[str]:
        """Return list of discovered audio files for downstream processing."""
        return list(self.ingest.list_audio_paths(target_date))
