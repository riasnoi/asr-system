#!/usr/bin/env bash
set -euo pipefail

: "${REMOTE_APP_DIR:?REMOTE_APP_DIR is required}"
: "${ASR_ONLINE_IMAGE:?ASR_ONLINE_IMAGE is required}"
: "${ASR_BATCH_IMAGE:?ASR_BATCH_IMAGE is required}"
: "${GHCR_USERNAME:?GHCR_USERNAME is required}"
: "${GHCR_TOKEN:?GHCR_TOKEN is required}"
: "${VAULT_ADDR:?VAULT_ADDR is required}"
: "${VAULT_ROLE_ID:?VAULT_ROLE_ID is required}"
: "${VAULT_SECRET_ID:?VAULT_SECRET_ID is required}"

cd "${REMOTE_APP_DIR}"

# Generate .env with Vault bootstrap credentials (no application secrets on disk).
cat > .env <<EOF
APP_ENV=prod
VAULT_ENABLED=true
VAULT_ADDR=${VAULT_ADDR}
VAULT_AUTH_METHOD=approle
VAULT_ROLE_ID=${VAULT_ROLE_ID}
VAULT_SECRET_ID=${VAULT_SECRET_ID}
VAULT_MOUNT_POINT=secret
VAULT_BASE_PATH=asr-system
EOF
chmod 600 .env

echo "${GHCR_TOKEN}" | docker login ghcr.io -u "${GHCR_USERNAME}" --password-stdin

docker compose -f deploy/production/docker-compose.yml pull online
docker pull "${ASR_BATCH_IMAGE}"
docker compose -f deploy/production/docker-compose.yml up -d online airflow-db airflow-webserver airflow-scheduler

curl -fsS http://127.0.0.1:8080/health >/dev/null
docker exec airflow-webserver airflow dags list | grep -q nightly_asr_batch

echo "Deploy completed"
