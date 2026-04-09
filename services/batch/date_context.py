from __future__ import annotations

import os
from datetime import date


def resolve_target_date() -> date:
    explicit_target_date = os.environ.get("BATCH_TARGET_DATE", "").strip()
    if explicit_target_date:
        return date.fromisoformat(explicit_target_date)

    logical_date = os.environ.get("AIRFLOW_CTX_LOGICAL_DATE", "").strip()
    if logical_date:
        return date.fromisoformat(logical_date[:10])

    return date.today()
