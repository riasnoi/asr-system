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

default_args = {
    "owner": "ml-platform",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
}

BATCH_IMAGE = "asr-batch:placeholder"
NAMESPACE = "asr-system"

ENV_FROM = [
    V1EnvFromSource(config_map_ref=V1ConfigMapEnvSource(name="asr-config")),
    V1EnvFromSource(secret_ref=V1SecretEnvSource(name="asr-vault-credentials")),
]

DATA_VOLUME = V1Volume(
    name="data",
    persistent_volume_claim=V1PersistentVolumeClaimVolumeSource(
        claim_name="asr-data-pvc",
    ),
)

DATA_MOUNT = V1VolumeMount(name="data", mount_path="/app/data")

PULL_SECRETS = [V1LocalObjectReference(name="ghcr-pull-secret")]


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
        namespace=NAMESPACE,
        image=BATCH_IMAGE,
        cmds=["python", "-c"],
        arguments=[
            "import os, sys; "
            "d = __import__('datetime').date.today().isoformat(); "
            "inp = os.environ.get('BATCH_INPUT_DIR', './data/input'); "
            "day = os.path.join(inp, d); "
            "n = len([f for f in os.listdir(day) "
            "if f.endswith(('.wav','.mp3','.flac'))]) "
            "if os.path.isdir(day) else 0; "
            "print(f'validate: {n} recordings for {d}'); "
            "sys.exit(0 if n else 1)"
        ],
        env_from=ENV_FROM,
        volumes=[DATA_VOLUME],
        volume_mounts=[DATA_MOUNT],
        image_pull_secrets=PULL_SECRETS,
        is_delete_operator_pod=True,
        get_logs=True,
        execution_timeout=timedelta(minutes=5),
    )

    run_pipeline = KubernetesPodOperator(
        task_id="run_batch_pipeline",
        name="asr-batch-run",
        namespace=NAMESPACE,
        image=BATCH_IMAGE,
        cmds=["python", "services/batch/main.py"],
        env_from=ENV_FROM,
        volumes=[DATA_VOLUME],
        volume_mounts=[DATA_MOUNT],
        image_pull_secrets=PULL_SECRETS,
        is_delete_operator_pod=True,
        get_logs=True,
        execution_timeout=timedelta(hours=6),
        sla=timedelta(hours=8),
    )

    verify_results = KubernetesPodOperator(
        task_id="verify_results",
        name="asr-verify-results",
        namespace=NAMESPACE,
        image=BATCH_IMAGE,
        cmds=["python", "-c"],
        arguments=[
            "import os, sys; "
            "out = os.environ.get('BATCH_OUTPUT_DIR', './data/output'); "
            "scores = os.path.join(out, 'call_scores.jsonl'); "
            "ok = os.path.isfile(scores) and os.path.getsize(scores) > 0; "
            "print(f'verify: {scores} ok={ok}'); "
            "sys.exit(0 if ok else 1)"
        ],
        env_from=ENV_FROM,
        volumes=[DATA_VOLUME],
        volume_mounts=[DATA_MOUNT],
        image_pull_secrets=PULL_SECRETS,
        is_delete_operator_pod=True,
        get_logs=True,
        execution_timeout=timedelta(minutes=5),
    )

    report_summary = KubernetesPodOperator(
        task_id="report_summary",
        name="asr-report",
        namespace=NAMESPACE,
        image=BATCH_IMAGE,
        cmds=["python", "-c"],
        arguments=[
            "import os, json; "
            "out = os.environ.get('BATCH_OUTPUT_DIR', './data/output'); "
            "path = os.path.join(out, 'call_scores.jsonl'); "
            "scores = [json.loads(l) for l in open(path)]; "
            "avg = sum(s.get('overall_score', 0) for s in scores) / max(len(scores), 1); "
            "print(f'summary: {len(scores)} calls, avg_score={avg:.2f}')"
        ],
        env_from=ENV_FROM,
        volumes=[DATA_VOLUME],
        volume_mounts=[DATA_MOUNT],
        image_pull_secrets=PULL_SECRETS,
        is_delete_operator_pod=True,
        get_logs=True,
        execution_timeout=timedelta(minutes=5),
    )

    validate_input >> run_pipeline >> verify_results >> report_summary
