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
    V1EnvFromSource,
    V1LocalObjectReference,
    V1PersistentVolumeClaimVolumeSource,
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

_DATA_VOLUME = V1Volume(
    name="data",
    persistent_volume_claim=V1PersistentVolumeClaimVolumeSource(claim_name="asr-data-pvc"),
)

_DATA_MOUNT = V1VolumeMount(name="data", mount_path="/app/data")

_PULL_SECRETS = [V1LocalObjectReference(name="ghcr-pull-secret")]

_COMMON = dict(
    namespace=NAMESPACE,
    image=BATCH_IMAGE,
    env_from=_ENV_FROM,
    volumes=[_DATA_VOLUME],
    volume_mounts=[_DATA_MOUNT],
    image_pull_secrets=_PULL_SECRETS,
    is_delete_operator_pod=True,
    get_logs=True,
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
        cmds=["python", "-c"],
        arguments=[
            "import os, sys; "
            "d = __import__('datetime').date.today().isoformat(); "
            "bucket = os.environ.get('BATCH_S3_BUCKET', ''); "
            "n = 0; "
            "exts = ('.wav', '.mp3', '.flac'); "
            "if bucket: "
            "  import boto3; "
            "  s3 = boto3.client('s3', "
            "    aws_access_key_id=os.environ.get('BATCH_STORAGE_ACCESS_KEY'), "
            "    aws_secret_access_key=os.environ.get('BATCH_STORAGE_SECRET_KEY'), "
            "    endpoint_url=os.environ.get('BATCH_S3_ENDPOINT_URL') or None, "
            "    region_name=os.environ.get('BATCH_S3_REGION', 'us-east-1')); "
            "  prefix = os.environ.get('BATCH_S3_PREFIX', 'recordings').rstrip('/') + '/' + d + '/'; "
            "  pages = s3.get_paginator('list_objects_v2').paginate(Bucket=bucket, Prefix=prefix); "
            "  n = sum(1 for p in pages for o in p.get('Contents', []) "
            "    if any(o['Key'].endswith(e) for e in exts)); "
            "else: "
            "  import os as _os; "
            "  inp = os.environ.get('BATCH_INPUT_DIR', './data/input'); "
            "  day = _os.path.join(inp, d); "
            "  n = len([f for f in _os.listdir(day) if f.endswith(exts)]) "
            "    if _os.path.isdir(day) else 0; "
            "src = f's3://{bucket}' if bucket else 'local'; "
            "print(f'validate [{src}]: {n} recordings for {d}'); "
            "sys.exit(0 if n else 1)"
        ],
        execution_timeout=timedelta(minutes=5),
        **_COMMON,
    )

    run_batch_pipeline = KubernetesPodOperator(
        task_id="run_batch_pipeline",
        name="asr-batch-run",
        cmds=["python", "services/batch/main.py"],
        execution_timeout=timedelta(hours=6),
        sla=timedelta(hours=8),
        **_COMMON,
    )

    verify_results = KubernetesPodOperator(
        task_id="verify_results",
        name="asr-verify-results",
        cmds=["python", "-c"],
        arguments=[
            "import os, sys; "
            "out = os.environ.get('BATCH_OUTPUT_DIR', './data/output'); "
            "scores = os.path.join(out, 'call_scores.jsonl'); "
            "ok = os.path.isfile(scores) and os.path.getsize(scores) > 0; "
            "print(f'verify: {scores} ok={ok}'); "
            "sys.exit(0 if ok else 1)"
        ],
        execution_timeout=timedelta(minutes=5),
        **_COMMON,
    )

    report_summary = KubernetesPodOperator(
        task_id="report_summary",
        name="asr-report",
        cmds=["python", "-c"],
        arguments=[
            "import os, json; "
            "out = os.environ.get('BATCH_OUTPUT_DIR', './data/output'); "
            "path = os.path.join(out, 'call_scores.jsonl'); "
            "scores = [json.loads(l) for l in open(path)]; "
            "avg = sum(s.get('overall_score', 0) for s in scores) / max(len(scores), 1); "
            "print(f'summary: {len(scores)} calls, avg_score={avg:.2f}')"
        ],
        execution_timeout=timedelta(minutes=5),
        **_COMMON,
    )

    validate_input >> run_batch_pipeline >> verify_results >> report_summary
