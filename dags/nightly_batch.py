"""Nightly ASR batch DAG.

Uses KubernetesPodOperator to run each pipeline stage in an isolated pod.
Logs are streamed back to Airflow in real time and stored on a persistent
volume so they survive scheduler pod restarts.

Pipeline:
  validate_input → run_batch_pipeline → verify_results → report_summary
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client import (
    V1ConfigMapEnvSource,
    V1EmptyDirVolumeSource,
    V1EnvFromSource,
    V1LocalObjectReference,
    V1SecretEnvSource,
    V1Volume,
    V1VolumeMount,
)

NAMESPACE = "asr-system"
BATCH_IMAGE = "asr-batch:placeholder"

default_args = {
    "owner": "ml-platform",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=15),
}

_ENV_FROM = [
    V1EnvFromSource(config_map_ref=V1ConfigMapEnvSource(name="asr-config")),
    V1EnvFromSource(secret_ref=V1SecretEnvSource(name="asr-vault-credentials")),
]

_PULL_SECRETS = [V1LocalObjectReference(name="ghcr-pull-secret")]


_SCRATCH_VOLUME = V1Volume(name="data", empty_dir=V1EmptyDirVolumeSource())
_SCRATCH_MOUNT = V1VolumeMount(name="data", mount_path="/app/data")

_COMMON = dict(
    namespace=NAMESPACE,
    image=BATCH_IMAGE,
    env_from=_ENV_FROM,
    image_pull_secrets=_PULL_SECRETS,
    is_delete_operator_pod=True,
    get_logs=True,
)

_COMMON_WITH_SCRATCH = dict(
    **_COMMON,
    volumes=[_SCRATCH_VOLUME],
    volume_mounts=[_SCRATCH_MOUNT],
)


with DAG(
    dag_id="nightly_asr_batch",
    description="Nightly processing of call-center recordings",
    default_args=default_args,
    schedule="0 0 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["asr", "batch", "nightly"],
) as dag:

    validate_input = KubernetesPodOperator(
        task_id="validate_input",
        name="asr-validate-input",
        cmds=["python", "services/batch/validate.py"],
        execution_timeout=timedelta(minutes=5),
        **_COMMON,
    )

    run_batch_pipeline = KubernetesPodOperator(
        task_id="run_batch_pipeline",
        name="asr-batch-run",
        cmds=["python", "services/batch/main.py"],
        execution_timeout=timedelta(hours=6),
        sla=timedelta(hours=8),
        **_COMMON_WITH_SCRATCH,
    )

    verify_results = KubernetesPodOperator(
        task_id="verify_results",
        name="asr-verify-results",
        cmds=["python", "services/batch/verify.py"],
        execution_timeout=timedelta(minutes=5),
        **_COMMON,
    )

    report_summary = KubernetesPodOperator(
        task_id="report_summary",
        name="asr-report",
        cmds=["python", "services/batch/report.py"],
        execution_timeout=timedelta(minutes=5),
        **_COMMON,
    )

    validate_input >> run_batch_pipeline >> verify_results >> report_summary
