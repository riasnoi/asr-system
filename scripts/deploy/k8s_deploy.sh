#!/usr/bin/env bash
set -euo pipefail

export KUBECONFIG="${HOME}/.kube/config"

: "${REMOTE_APP_DIR:?REMOTE_APP_DIR is required}"
: "${ONLINE_IMAGE:?ONLINE_IMAGE is required}"
: "${BATCH_IMAGE:?BATCH_IMAGE is required}"
: "${AIRFLOW_IMAGE:?AIRFLOW_IMAGE is required}"
: "${GHCR_USERNAME:?GHCR_USERNAME is required}"
: "${GHCR_TOKEN:?GHCR_TOKEN is required}"

NAMESPACE="asr-system"
K8S_DIR="${REMOTE_APP_DIR}/deploy/k8s/base"

# ---------------------------------------------------------------------------
# Read ASR DB credentials from Vault.
# vault CLI resolves the token automatically: VAULT_TOKEN env var takes
# priority, then ~/.vault-token (written by any prior "vault login" or
# "vault token create" on the server).  No extra setup is required if the
# deploy user already has an active Vault session.
# ---------------------------------------------------------------------------
VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
VAULT_MOUNT="${VAULT_MOUNT_POINT:-secret}"
export VAULT_ADDR

echo "==> Reading ASR DB credentials from Vault (${VAULT_ADDR})"
# vault read with the explicit /data/ path bypasses the sys/internal/ui/mounts
# discovery request, so a minimal read-only policy is sufficient.
ASR_DB_USER=$(vault read -field=POSTGRES_USER "${VAULT_MOUNT}/data/asr-system/app")
ASR_DB_PASSWORD=$(vault read -field=POSTGRES_PASSWORD "${VAULT_MOUNT}/data/asr-system/app")
: "${ASR_DB_USER:?POSTGRES_USER not found in Vault at ${VAULT_MOUNT}/data/asr-system/app}"
: "${ASR_DB_PASSWORD:?POSTGRES_PASSWORD not found in Vault at ${VAULT_MOUNT}/data/asr-system/app}"

echo "==> Ensuring namespace exists"
kubectl create namespace "${NAMESPACE}" 2>/dev/null || true

echo "==> Creating GHCR pull secret"
kubectl -n "${NAMESPACE}" delete secret ghcr-pull-secret --ignore-not-found
kubectl -n "${NAMESPACE}" create secret docker-registry ghcr-pull-secret \
  --docker-server=ghcr.io \
  --docker-username="${GHCR_USERNAME}" \
  --docker-password="${GHCR_TOKEN}"

echo "==> Creating ASR DB credentials secret"
kubectl -n "${NAMESPACE}" delete secret asr-db-credentials --ignore-not-found
kubectl -n "${NAMESPACE}" create secret generic asr-db-credentials \
  --from-literal=POSTGRES_USER="${ASR_DB_USER}" \
  --from-literal=POSTGRES_PASSWORD="${ASR_DB_PASSWORD}"

echo "==> Rendering manifests with image overrides"
cd "${K8S_DIR}"

# kubectl kustomize does not support 'edit set image', so we render and
# replace image placeholders with the actual GHCR image URIs.
kubectl kustomize . \
  | sed "s|asr-online:placeholder|${ONLINE_IMAGE}|g" \
  | sed "s|asr-batch:placeholder|${BATCH_IMAGE}|g" \
  | sed "s|asr-airflow:placeholder|${AIRFLOW_IMAGE}|g" \
  | kubectl apply -f -

collect_diagnostics() {
  local label="$1"
  echo ""
  echo "!!! Rollout failed for ${label} — collecting diagnostics"
  echo "--- Pod status ---"
  kubectl -n "${NAMESPACE}" get pods -l "app=${label}" -o wide
  echo "--- Pod descriptions and logs ---"
  for pod in $(kubectl -n "${NAMESPACE}" get pods -l "app=${label}" -o jsonpath='{.items[*].metadata.name}'); do
    echo "=== describe ${pod} ==="
    kubectl -n "${NAMESPACE}" describe pod "${pod}" | tail -25
    echo "=== logs ${pod} ==="
    kubectl -n "${NAMESPACE}" logs "${pod}" --tail=40 2>&1 || true
  done
}

echo "==> Restarting deployments to pick up ConfigMap changes"
kubectl -n "${NAMESPACE}" rollout restart deployment/asr-online
kubectl -n "${NAMESPACE}" rollout restart deployment/airflow-webserver
kubectl -n "${NAMESPACE}" rollout restart deployment/airflow-scheduler

echo "==> Waiting for online deployment rollout"
if ! kubectl -n "${NAMESPACE}" rollout status deployment/asr-online --timeout=300s; then
  collect_diagnostics "asr-online"
  exit 1
fi

echo "==> Waiting for ASR DB"
kubectl -n "${NAMESPACE}" rollout status statefulset/asr-db --timeout=120s

echo "==> Waiting for Airflow DB"
kubectl -n "${NAMESPACE}" rollout status statefulset/airflow-db --timeout=120s

echo "==> Waiting for Airflow webserver"
if ! kubectl -n "${NAMESPACE}" rollout status deployment/airflow-webserver --timeout=300s; then
  collect_diagnostics "airflow-webserver"
  exit 1
fi

echo "==> Waiting for Airflow scheduler"
if ! kubectl -n "${NAMESPACE}" rollout status deployment/airflow-scheduler --timeout=300s; then
  collect_diagnostics "airflow-scheduler"
  exit 1
fi

echo "==> Verifying pods"
kubectl -n "${NAMESPACE}" get pods

echo "==> Deploy completed successfully"
