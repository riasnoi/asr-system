"""Read call scores from the repository and print a summary for the target date."""

from asr_system.config import get_settings
from asr_system.infrastructure.factory import create_repository_adapters
from asr_system.logging_config import setup_logging
from services.batch.date_context import resolve_target_date

settings = get_settings()
setup_logging(settings.app.log_level)

target_date = resolve_target_date()

_, scores_repo = create_repository_adapters(settings)
scores = scores_repo.list_all()

day_scores = [s for s in scores if s.updated_at.date() == target_date]

n = len(day_scores)
avg = sum(s.overall_score for s in day_scores) / max(n, 1)
print(f"summary: {n} calls processed on {target_date}, avg_score={avg:.1f}")
