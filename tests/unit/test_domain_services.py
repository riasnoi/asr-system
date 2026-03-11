from datetime import UTC, datetime

from asr_system.domain.entities import Utterance
from asr_system.domain.services import build_call_score
from asr_system.domain.value_objects import Emotion


def test_build_call_score_calculates_negative_ratios_by_speaker() -> None:
    utterances = [
        Utterance("call-1", "client", 0, 1, "a", Emotion.ANGRY, 0.9),
        Utterance("call-1", "client", 1, 2, "b", Emotion.NEUTRAL, 0.8),
        Utterance("call-1", "operator", 2, 3, "c", Emotion.SAD, 0.7),
        Utterance("call-1", "operator", 3, 4, "d", Emotion.POSITIVE, 0.6),
    ]

    score = build_call_score("call-1", utterances)

    assert score.call_id == "call-1"
    assert score.negative_index_client == 0.5
    assert score.negative_index_operator == 0.5
    assert isinstance(score.updated_at, datetime)
    assert score.updated_at.tzinfo == UTC
