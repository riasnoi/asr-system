from dataclasses import asdict, dataclass, field
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
    # Composite quality score (0–100)
    overall_score: float = field(default=0.0)
    # How satisfied the client sounded (0–100)
    client_satisfaction: float = field(default=0.0)
    # How professionally the operator conducted themselves (0–100)
    operator_quality: float = field(default=0.0)
    # Fraction of total speech time attributed to the operator (0–1)
    talk_ratio_operator: float = field(default=0.5)
    # Total audio duration covered by utterances in seconds
    total_duration_seconds: float = field(default=0.0)

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["updated_at"] = self.updated_at.isoformat()
        return data
