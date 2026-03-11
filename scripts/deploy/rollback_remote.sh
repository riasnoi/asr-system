#!/usr/bin/env bash
set -euo pipefail

: "${REMOTE_APP_DIR:?REMOTE_APP_DIR is required}"
: "${ASR_ONLINE_IMAGE:?ASR_ONLINE_IMAGE is required}"

cd "${REMOTE_APP_DIR}"

docker compose -f deploy/production/docker-compose.yml up -d online

curl -fsS http://127.0.0.1:8080/health >/dev/null

echo "Rollback completed"
