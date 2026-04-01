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

echo "==> Ensuring namespace exists"
kubectl create namespace "${NAMESPACE}" 2>/dev/null || true

echo "==> Creating GHCR pull secret"
kubectl -n "${NAMESPACE}" delete secret ghcr-pull-secret --ignore-not-found
kubectl -n "${NAMESPACE}" create secret docker-registry ghcr-pull-secret \
  --docker-server=ghcr.io \
  --docker-username="${GHCR_USERNAME}" \
  --docker-password="${GHCR_TOKEN}"

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
