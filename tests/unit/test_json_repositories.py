from datetime import UTC, datetime

from asr_system.domain.entities import CallScore, Utterance
from asr_system.domain.value_objects import Emotion
from asr_system.infrastructure.repositories.json_store import (
    JsonCallScoreRepository,
    JsonUtteranceRepository,
)


def test_json_repositories_save_and_read(tmp_path) -> None:
    utter_repo = JsonUtteranceRepository(str(tmp_path))
    score_repo = JsonCallScoreRepository(str(tmp_path))

    utter_repo.save_many(
        [Utterance("call-7", "client", 0, 1, "hi", Emotion.NEUTRAL, 0.5)]
    )
    score_repo.save(
        CallScore(
            call_id="call-7",
            negative_index_client=0.2,
            negative_index_operator=0.3,
            updated_at=datetime(2026, 3, 11, tzinfo=UTC),
        )
    )

    utterances = utter_repo.get_by_call_id("call-7")
    score = score_repo.get("call-7")

    assert len(utterances) == 1
    assert utterances[0].emotion == Emotion.NEUTRAL
    assert score is not None
    assert score.negative_index_operator == 0.3
