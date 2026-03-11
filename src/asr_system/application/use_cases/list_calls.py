from dataclasses import dataclass

from asr_system.domain.ports import CallScoreRepositoryPort


@dataclass
class ListCallsUseCase:
    scores_repo: CallScoreRepositoryPort

    def execute(self, min_negative_index: float = 0.0) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for item in self.scores_repo.list_all():
            if max(item.negative_index_client, item.negative_index_operator) >= min_negative_index:
                result.append(item.to_dict())
        return result
