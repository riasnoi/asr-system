"""Read call_scores.jsonl from S3 and print a summary for the target date."""

import json
import os
from datetime import date

import boto3

from asr_system.config import get_settings

raw = os.environ.get("AIRFLOW_CTX_LOGICAL_DATE", "")
d = raw[:10] if raw else date.today().isoformat()

settings = get_settings()
key = f"results/{d}/call_scores.jsonl"

client = boto3.client(
    "s3",
    aws_access_key_id=settings.batch_secrets.storage_access_key,
    aws_secret_access_key=settings.batch_secrets.storage_secret_key,
    endpoint_url=settings.s3.endpoint_url or None,
    region_name=settings.s3.region,
)

body = client.get_object(Bucket=settings.s3.bucket, Key=key)["Body"].read().decode()
scores = [json.loads(line) for line in body.strip().splitlines() if line.strip()]

n = len(scores)
avg = sum(s.get("overall_score", 0) for s in scores) / max(n, 1)
print(f"summary: {n} calls processed, avg_score={avg:.1f}")
