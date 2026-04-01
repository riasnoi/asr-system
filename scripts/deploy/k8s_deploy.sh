#!/usr/bin/env bash
set -euo pipefail

export KUBECONFIG="${HOME}/.kube/config"

: "${REMOTE_APP_DIR:?REMOTE_APP_DIR is required}"
: "${ONLINE_IMAGE:?ONLINE_IMAGE is required}"
: "${BATCH_IMAGE:?BATCH_IMAGE is required}"
: "${GHCR_USERNAME:?GHCR_USERNAME is required}"
: "${GHCR_TOKEN:?GHCR_TOKEN is required}"

NAMESPACE="asr-system"
K8S_DIR="${REMOTE_APP_DIR}/deploy/k8s/base"

echo "==> Ensuring namespace exists"
kubectl get namespace "${NAMESPACE}" >/dev/null 2>&1 || kubectl create namespace "${NAMESPACE}"

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
  | sed "s|image: asr-online:placeholder|image: ${ONLINE_IMAGE}|g" \
  | sed "s|image: asr-batch:placeholder|image: ${BATCH_IMAGE}|g" \
  | kubectl apply -f -

echo "==> Waiting for online deployment rollout"
if ! kubectl -n "${NAMESPACE}" rollout status deployment/asr-online --timeout=300s; then
  echo ""
  echo "!!! Rollout failed — collecting diagnostics"
  echo "--- Pod status ---"
  kubectl -n "${NAMESPACE}" get pods -l app=asr-online -o wide
  echo "--- Recent pod events ---"
  kubectl -n "${NAMESPACE}" get events --sort-by='.lastTimestamp' --field-selector involvedObject.kind=Pod | tail -30
  echo "--- Pod descriptions ---"
  for pod in $(kubectl -n "${NAMESPACE}" get pods -l app=asr-online -o jsonpath='{.items[*].metadata.name}'); do
    echo "=== describe ${pod} ==="
    kubectl -n "${NAMESPACE}" describe pod "${pod}" | tail -25
    echo "=== logs ${pod} ==="
    kubectl -n "${NAMESPACE}" logs "${pod}" --tail=40 2>&1 || true
  done
  exit 1
fi

echo "==> Verifying pods"
kubectl -n "${NAMESPACE}" get pods -l app=asr-online

echo "==> Deploy completed successfully"
