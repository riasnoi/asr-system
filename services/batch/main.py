from datetime import date

from asr_system.config import get_settings
from asr_system.logging_config import setup_logging

if __name__ == "__main__":
    settings = get_settings()
    setup_logging(settings.app.log_level)

    from asr_system.interfaces.batch.runner import BatchRunner

    processed = BatchRunner().run(date.today())
    print(f"processed_calls={len(processed)}")
