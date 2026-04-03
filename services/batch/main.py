import os
from datetime import date

from asr_system.config import get_settings
from asr_system.logging_config import setup_logging

if __name__ == "__main__":
    settings = get_settings()
    setup_logging(settings.app.log_level)

    # Respect Airflow logical date when running inside a KubernetesPodOperator.
    # Falls back to today for local / manual runs.
    raw = os.environ.get("AIRFLOW_CTX_LOGICAL_DATE", "")
    target_date = date.fromisoformat(raw[:10]) if raw else date.today()

    from asr_system.interfaces.batch.runner import BatchRunner

    processed = BatchRunner().run(target_date)
    print(f"processed_calls={len(processed)} date={target_date}")
