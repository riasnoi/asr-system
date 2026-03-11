from dataclasses import asdict, dataclass
from datetime import datetime

from .value_objects import Emotion


@dataclass(frozen=True)
class Utterance:
    call_id: str
    speaker: str
    start_sec: float
    end_sec: float
    text: str
    emotion: Emotion
    confidence: float

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["emotion"] = self.emotion.value
        return data


@dataclass(frozen=True)
class CallScore:
    call_id: str
    negative_index_client: float
    negative_index_operator: float
    updated_at: datetime

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["updated_at"] = self.updated_at.isoformat()
        return data
