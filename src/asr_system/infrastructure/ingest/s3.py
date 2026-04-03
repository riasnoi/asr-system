"""S3 ingest adapter: downloads audio files for a given date to local storage."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import boto3
from botocore.config import Config

from asr_system.domain.ports import IngestPort

logger = logging.getLogger(__name__)

_AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac"}


class S3Ingest(IngestPort):
    """Downloads audio files from S3 bucket/<prefix>/<YYYY-MM-DD>/ to local input_dir.

    Files that already exist locally are skipped (idempotent download).
    """

    def __init__(
        self,
        bucket: str,
        access_key: str,
        secret_key: str,
        local_input_dir: str,
        prefix: str = "recordings",
        endpoint_url: str = "",
        region: str = "us-east-1",
    ) -> None:
        self._bucket = bucket
        self._prefix = prefix.rstrip("/")
        self._local_base = Path(local_input_dir)

        session = boto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        self._s3 = session.client(
            "s3",
            endpoint_url=endpoint_url or None,
            config=Config(signature_version="s3v4"),
        )
        logger.info(
            "S3Ingest configured: bucket=%s prefix=%s endpoint=%s",
            bucket,
            prefix,
            endpoint_url or "aws-default",
        )

    def list_audio_paths(self, target_date: date) -> list[str]:
        date_str = target_date.isoformat()
        s3_prefix = f"{self._prefix}/{date_str}/"
        local_dir = self._local_base / date_str
        local_dir.mkdir(parents=True, exist_ok=True)

        paginator = self._s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=self._bucket, Prefix=s3_prefix)

        downloaded: list[str] = []
        for page in pages:
            for obj in page.get("Contents", []):
                key: str = obj["Key"]
                if Path(key).suffix.lower() not in _AUDIO_EXTENSIONS:
                    continue

                filename = Path(key).name
                local_path = local_dir / filename

                if not local_path.exists():
                    logger.info("Downloading s3://%s/%s → %s", self._bucket, key, local_path)
                    self._s3.download_file(self._bucket, key, str(local_path))
                else:
                    logger.debug("Already exists, skipping: %s", local_path)

                downloaded.append(str(local_path))

        logger.info("S3Ingest: %d files for %s", len(downloaded), date_str)
        return sorted(downloaded)
