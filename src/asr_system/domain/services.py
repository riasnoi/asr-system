from collections import defaultdict

from .entities import CallScore, Utterance
from .value_objects import Emotion


def build_call_score(call_id: str, utterances: list[Utterance]) -> CallScore:
    """Calculate negative indexes separately for client and operator."""
    totals: dict[str, int] = defaultdict(int)
    negatives: dict[str, int] = defaultdict(int)

    for item in utterances:
        totals[item.speaker] += 1
        if item.emotion in {Emotion.ANGRY, Emotion.SAD}:
            negatives[item.speaker] += 1

    def ratio(speaker: str) -> float:
        total = totals[speaker]
        if total == 0:
            return 0.0
        return negatives[speaker] / total

    from datetime import datetime, UTC

    return CallScore(
        call_id=call_id,
        negative_index_client=ratio("client"),
        negative_index_operator=ratio("operator"),
        updated_at=datetime.now(tz=UTC),
    )
