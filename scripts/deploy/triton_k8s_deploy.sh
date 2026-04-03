#!/usr/bin/env bash
set -euo pipefail

export KUBECONFIG="${KUBECONFIG:-${HOME}/.kube/config}"

: "${TRITON_REMOTE_APP_DIR:?TRITON_REMOTE_APP_DIR is required}"
: "${TRITON_IMAGE:?TRITON_IMAGE is required}"
: "${GHCR_USERNAME:?GHCR_USERNAME is required}"
: "${GHCR_TOKEN:?GHCR_TOKEN is required}"

K8S_DIR="${TRITON_REMOTE_APP_DIR}/deploy/triton/k8s"
REPO_DIR="${TRITON_REMOTE_APP_DIR}/deploy/triton/model_repository"
SYNC_MODEL_REPOSITORY="${SYNC_MODEL_REPOSITORY:-false}"
NAMESPACE="ml-inference"

echo "==> Ensuring namespace exists"
kubectl apply -f "${K8S_DIR}/namespace.yaml"

echo "==> Creating GHCR pull secret"
kubectl -n "${NAMESPACE}" delete secret ghcr-pull-secret --ignore-not-found
kubectl -n "${NAMESPACE}" create secret docker-registry ghcr-pull-secret \
  --docker-server=ghcr.io \
  --docker-username="${GHCR_USERNAME}" \
  --docker-password="${GHCR_TOKEN}"

echo "==> Applying PVC and Service"
kubectl apply -f "${K8S_DIR}/triton-pvc.yaml"
kubectl apply -f "${K8S_DIR}/triton-service.yaml"

echo "==> Applying Deployment with image ${TRITON_IMAGE}"
# Подставляем реальный образ вместо placeholder; rollout случится только если spec изменился.
sed "s|triton-asr:placeholder|${TRITON_IMAGE}|g" "${K8S_DIR}/triton-deployment.yaml" \
  | kubectl apply -f -

echo "==> Waiting for rollout (no-op if nothing changed)"
kubectl -n "${NAMESPACE}" rollout status deployment/triton --timeout=600s

sync_repo() {
  if [[ "${SYNC_MODEL_REPOSITORY}" != "true" && "${SYNC_MODEL_REPOSITORY}" != "True" ]]; then
    return 0
  fi
  if [[ ! -d "${REPO_DIR}" ]]; then
    echo "ERROR: ${REPO_DIR} not found; cannot sync model_repository" >&2
    exit 1
  fi
  echo "==> Syncing model_repository into Triton pod /models (explicit opt-in)"
  kubectl -n "${NAMESPACE}" wait --for=condition=ready pod -l app=triton --timeout=300s
  local pod
  pod=$(kubectl -n "${NAMESPACE}" get pod -l app=triton -o jsonpath='{.items[0].metadata.name}')
  kubectl -n "${NAMESPACE}" cp "${REPO_DIR}/." "${pod}:/models/"
  echo "==> model_repository copied"

  echo "==> Restarting Triton so it picks up new models"
  kubectl -n "${NAMESPACE}" rollout restart deployment/triton
  kubectl -n "${NAMESPACE}" rollout status deployment/triton --timeout=600s
}

sync_repo

echo "==> Verifying pods"
kubectl -n "${NAMESPACE}" get pods

echo "==> Done"
