from dataclasses import dataclass

from asr_system.domain.ports import CallScoreRepositoryPort, UtteranceRepositoryPort


@dataclass
class GetCallCardUseCase:
    utterances_repo: UtteranceRepositoryPort
    scores_repo: CallScoreRepositoryPort

    def execute(self, call_id: str) -> dict:
        utterances = self.utterances_repo.get_by_call_id(call_id)
        score = self.scores_repo.get(call_id)
        return {
            "call_id": call_id,
            "utterances": [u.__dict__ for u in utterances],
            "score": score.__dict__ if score else None,
        }
