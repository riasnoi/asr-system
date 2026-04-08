from collections import defaultdict
from datetime import UTC, datetime

from .entities import CallScore, Utterance
from .value_objects import Emotion

_NEGATIVE_EMOTIONS = {Emotion.ANGRY, Emotion.SAD}


def build_call_score(call_id: str, utterances: list[Utterance]) -> CallScore:
    """Build a comprehensive quality score for a call.

    Metrics:
    - negative_index_* : fraction of angry/sad utterances per speaker.
    - client_satisfaction (0-100): starts at 50, boosted by positive utterances,
      penalised by negative ones.
    - operator_quality (0-100): how professionally the operator sounded;
      penalised for anger/sadness, rewarded for positivity.
    - talk_ratio_operator (0-1): operator's share of total speech duration;
      a balanced call has ~0.5.
    - overall_score (0-100): weighted composite of the three above plus a
      talk-balance bonus.
    """
    totals: dict[str, int] = defaultdict(int)
    neg_counts: dict[str, int] = defaultdict(int)
    pos_counts: dict[str, int] = defaultdict(int)
    duration: dict[str, float] = defaultdict(float)

    for item in utterances:
        totals[item.speaker] += 1
        if item.emotion in _NEGATIVE_EMOTIONS:
            neg_counts[item.speaker] += 1
        if item.emotion == Emotion.POSITIVE:
            pos_counts[item.speaker] += 1
        duration[item.speaker] += max(0.0, item.end_sec - item.start_sec)

    def _neg_ratio(speaker: str) -> float:
        t = totals[speaker]
        return neg_counts[speaker] / t if t else 0.0

    def _pos_ratio(speaker: str) -> float:
        t = totals[speaker]
        return pos_counts[speaker] / t if t else 0.0

    neg_client = _neg_ratio("client")
    neg_operator = _neg_ratio("operator")
    pos_client = _pos_ratio("client")
    pos_operator = _pos_ratio("operator")

    # Client satisfaction: neutral baseline 50, positive utterances push it up,
    # negative utterances push it down.
    client_satisfaction = round(
        max(0.0, min(100.0, 50.0 + pos_client * 50.0 - neg_client * 60.0)), 1
    )

    # Operator quality: starts at 100, penalised for anger/sadness, rewarded
    # for actively positive language.
    operator_quality = round(
        max(0.0, min(100.0, 100.0 - neg_operator * 70.0 + pos_operator * 20.0)), 1
    )

    # Talk-balance bonus: ideal operator share is ~50 %. Deviations shrink the
    # bonus linearly; it reaches 0 at ≤25 % or ≥75 % operator share.
    total_dur = sum(duration.values())
    talk_ratio_op = duration["operator"] / total_dur if total_dur > 0 else 0.5
    balance_bonus = max(0.0, 1.0 - abs(talk_ratio_op - 0.5) * 4.0)

    overall = round(
        0.50 * client_satisfaction
        + 0.35 * operator_quality
        + 0.15 * balance_bonus * 100.0,
        1,
    )

    return CallScore(
        call_id=call_id,
        negative_index_client=neg_client,
        negative_index_operator=neg_operator,
        updated_at=datetime.now(tz=UTC),
        overall_score=overall,
        client_satisfaction=client_satisfaction,
        operator_quality=operator_quality,
        talk_ratio_operator=round(talk_ratio_op, 4),
        total_duration_seconds=round(total_dur, 2),
    )
