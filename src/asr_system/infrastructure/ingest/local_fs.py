from datetime import date
from pathlib import Path

from asr_system.domain.ports import IngestPort


class LocalFsIngest(IngestPort):
    def __init__(self, input_dir: str) -> None:
        self.base = Path(input_dir)

    def list_audio_paths(self, target_date: date) -> list[str]:
        day_folder = self.base / target_date.isoformat()
        if not day_folder.exists():
            return []

        files = sorted(
            [
                p
                for p in day_folder.iterdir()
                if p.is_file() and p.suffix.lower() in {".wav", ".mp3", ".flac"}
            ]
        )
        return [str(path) for path in files]
