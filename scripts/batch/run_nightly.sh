#!/usr/bin/env bash
set -euo pipefail

TARGET_DATE="${1:-$(date -d 'yesterday' +%F)}"
export TARGET_DATE

# Idempotency key is TARGET_DATE; the application layer should treat existing call_id as upsert.
uv run python -c "from datetime import date; from asr_system.interfaces.batch.runner import BatchRunner; BatchRunner().run(date.fromisoformat('${TARGET_DATE}'))"
