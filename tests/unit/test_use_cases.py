from datetime import UTC, date, datetime

from asr_system.application.use_cases.batch_process_calls import BatchProcessCallsUseCase
from asr_system.application.use_cases.get_call_card import GetCallCardUseCase
from asr_system.application.use_cases.list_calls import ListCallsUseCase
from asr_system.application.use_cases.process_call import ProcessCallUseCase
from asr_system.domain.entities import CallScore, Utterance
from asr_system.domain.value_objects import Emotion


class StubIngest:
    def list_audio_paths(self, target_date: date) -> list[str]:
        assert target_date == date(2026, 3, 10)
        return ["/tmp/a.wav", "/tmp/b.wav"]


class StubAsr:
    def transcribe(self, audio_path: str) -> list[tuple[float, float, str]]:
        return [(0.0, 1.0, f"segment {audio_path}"), (1.0, 2.0, "problem found")]


class StubSpeaker:
    def assign_speakers(
        self, segments: list[tuple[float, float, str]]
    ) -> list[tuple[float, float, str, str]]:
        return [
            (a, b, c, "client" if i % 2 else "operator") for i, (a, b, c) in enumerate(segments)
        ]


class StubEmotion:
    def classify(self, text: str) -> tuple[Emotion, float]:
        if "problem" in text:
            return Emotion.ANGRY, 0.9
        return Emotion.NEUTRAL, 0.8


class MemoryUtterancesRepo:
    def __init__(self) -> None:
        self.items: list[Utterance] = []

    def save_many(self, utterances: list[Utterance]) -> None:
        self.items.extend(utterances)

    def get_by_call_id(self, call_id: str) -> list[Utterance]:
        return [i for i in self.items if i.call_id == call_id]


class MemoryScoresRepo:
    def __init__(self) -> None:
        self.items: dict[str, CallScore] = {}

    def save(self, score: CallScore) -> None:
        self.items[score.call_id] = score

    def get(self, call_id: str) -> CallScore | None:
        return self.items.get(call_id)

    def list_all(self) -> list[CallScore]:
        return list(self.items.values())


def test_process_call_saves_utterances_and_score() -> None:
    utterances_repo = MemoryUtterancesRepo()
    scores_repo = MemoryScoresRepo()

    use_case = ProcessCallUseCase(
        asr=StubAsr(),
        speaker_attribution=StubSpeaker(),
        emotion=StubEmotion(),
        utterances_repo=utterances_repo,
        scores_repo=scores_repo,
    )

    call_id = use_case.execute("/tmp/call-01.wav")

    assert call_id == "call-01"
    assert len(utterances_repo.items) == 2
    assert scores_repo.get("call-01") is not None


def test_batch_process_calls_returns_all_processed_ids() -> None:
    utterances_repo = MemoryUtterancesRepo()
    scores_repo = MemoryScoresRepo()
    process_call = ProcessCallUseCase(
        asr=StubAsr(),
        speaker_attribution=StubSpeaker(),
        emotion=StubEmotion(),
        utterances_repo=utterances_repo,
        scores_repo=scores_repo,
    )
    use_case = BatchProcessCallsUseCase(ingest=StubIngest(), process_call=process_call)

    result = use_case.execute(date(2026, 3, 10))

    assert result == ["a", "b"]


def test_get_call_card_and_list_calls_work_with_scores() -> None:
    utterances_repo = MemoryUtterancesRepo()
    scores_repo = MemoryScoresRepo()
    utterances_repo.save_many(
        [
            Utterance("x", "client", 0, 1, "hello", Emotion.NEUTRAL, 0.7),
            Utterance("x", "operator", 1, 2, "problem", Emotion.ANGRY, 0.9),
        ]
    )
    scores_repo.save(
        CallScore(
            call_id="x",
            negative_index_client=0.0,
            negative_index_operator=1.0,
            updated_at=datetime(2026, 3, 11, tzinfo=UTC),
        )
    )

    card = GetCallCardUseCase(utterances_repo=utterances_repo, scores_repo=scores_repo).execute("x")
    calls = ListCallsUseCase(scores_repo=scores_repo).execute(min_negative_index=0.9)

    assert card["call_id"] == "x"
    assert len(card["utterances"]) == 2
    assert card["score"]["negative_index_operator"] == 1.0
    assert len(calls) == 1
    assert calls[0]["call_id"] == "x"
