from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator


default_args = {
    "owner": "ml-platform",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="nightly_asr_batch",
    description="Process call-center recordings for previous day",
    default_args=default_args,
    schedule="0 0 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["asr", "batch", "nightly"],
) as dag:
    run_batch = BashOperator(
        task_id="run_batch_pipeline",
        bash_command=(
            "TARGET_DATE=$(date -d 'yesterday' +%F) "
            "&& /opt/asr/scripts/batch/run_nightly.sh ${TARGET_DATE}"
        ),
        execution_timeout=timedelta(hours=7),
        sla=timedelta(hours=8),
    )

    verify_outputs = BashOperator(
        task_id="verify_batch_outputs",
        bash_command="test -s /opt/asr/data/output/call_scores.jsonl",
        execution_timeout=timedelta(minutes=5),
    )

    run_batch >> verify_outputs
