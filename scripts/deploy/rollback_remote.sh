#!/usr/bin/env bash
set -euo pipefail

export KUBECONFIG="${HOME}/.kube/config"

NAMESPACE="asr-system"

echo "==> Rolling back online deployment to previous revision"
kubectl -n "${NAMESPACE}" rollout undo deployment/asr-online

echo "==> Waiting for rollout"
kubectl -n "${NAMESPACE}" rollout status deployment/asr-online --timeout=120s

echo "==> Current pod status"
kubectl -n "${NAMESPACE}" get pods -l app=asr-online

echo "==> Current image"
kubectl -n "${NAMESPACE}" get deployment asr-online -o jsonpath='{.spec.template.spec.containers[0].image}'
echo

echo "==> Rollback completed"
