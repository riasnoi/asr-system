"""Validate that audio files exist for the target date (S3 or local)."""

import os
import sys
from datetime import date

raw = os.environ.get("AIRFLOW_CTX_LOGICAL_DATE", "")
d = raw[:10] if raw else date.today().isoformat()

bucket = os.environ.get("BATCH_S3_BUCKET", "")
exts = (".wav", ".mp3", ".flac")
n = 0

if bucket:
    import boto3

    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.environ.get("BATCH_STORAGE_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("BATCH_STORAGE_SECRET_KEY"),
        endpoint_url=os.environ.get("BATCH_S3_ENDPOINT_URL") or None,
        region_name=os.environ.get("BATCH_S3_REGION", "us-east-1"),
    )
    prefix = os.environ.get("BATCH_S3_PREFIX", "recordings").rstrip("/") + "/" + d + "/"
    pages = s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix)
    n = sum(
        1
        for page in pages
        for obj in page.get("Contents", [])
        if any(obj["Key"].endswith(e) for e in exts)
    )
else:
    inp = os.environ.get("BATCH_INPUT_DIR", "./data/input")
    day = os.path.join(inp, d)
    n = len([f for f in os.listdir(day) if f.endswith(exts)]) if os.path.isdir(day) else 0

src = f"s3://{bucket}" if bucket else "local"
print(f"validate [{src}]: {n} recordings for {d}")
sys.exit(0 if n else 1)
