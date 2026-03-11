import json
from datetime import datetime
from pathlib import Path
from typing import Sequence

from asr_system.domain.entities import CallScore, Utterance
from asr_system.domain.ports import CallScoreRepositoryPort, UtteranceRepositoryPort
from asr_system.domain.value_objects import Emotion


class JsonUtteranceRepository(UtteranceRepositoryPort):
    def __init__(self, root_dir: str) -> None:
        self.root = Path(root_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "utterances.jsonl"

    def save_many(self, utterances: Sequence[Utterance]) -> None:
        with self.path.open("a", encoding="utf-8") as file:
            for item in utterances:
                file.write(json.dumps(item.to_dict(), ensure_ascii=False) + "\n")

    def get_by_call_id(self, call_id: str) -> list[Utterance]:
        if not self.path.exists():
            return []

        items: list[Utterance] = []
        with self.path.open("r", encoding="utf-8") as file:
            for line in file:
                raw = json.loads(line)
                if raw["call_id"] != call_id:
                    continue
                items.append(
                    Utterance(
                        call_id=raw["call_id"],
                        speaker=raw["speaker"],
                        start_sec=raw["start_sec"],
                        end_sec=raw["end_sec"],
                        text=raw["text"],
                        emotion=Emotion(raw["emotion"]),
                        confidence=raw["confidence"],
                    )
                )
        return items


class JsonCallScoreRepository(CallScoreRepositoryPort):
    def __init__(self, root_dir: str) -> None:
        self.root = Path(root_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "call_scores.jsonl"

    def save(self, score: CallScore) -> None:
        # Replace existing call score by call_id.
        all_scores = {item.call_id: item for item in self.list_all()}
        all_scores[score.call_id] = score
        with self.path.open("w", encoding="utf-8") as file:
            for item in all_scores.values():
                file.write(json.dumps(item.to_dict(), ensure_ascii=False) + "\n")

    def get(self, call_id: str) -> CallScore | None:
        for item in self.list_all():
            if item.call_id == call_id:
                return item
        return None

    def list_all(self) -> list[CallScore]:
        if not self.path.exists():
            return []

        result: list[CallScore] = []
        with self.path.open("r", encoding="utf-8") as file:
            for line in file:
                raw = json.loads(line)
                result.append(
                    CallScore(
                        call_id=raw["call_id"],
                        negative_index_client=raw["negative_index_client"],
                        negative_index_operator=raw["negative_index_operator"],
                        updated_at=datetime.fromisoformat(raw["updated_at"]),
                    )
                )
        return result
