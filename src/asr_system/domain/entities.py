from dataclasses import dataclass
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


@dataclass(frozen=True)
class CallScore:
    call_id: str
    negative_index_client: float
    negative_index_operator: float
    updated_at: datetime
