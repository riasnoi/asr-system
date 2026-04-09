import logging
from datetime import date
from pathlib import Path

from asr_system.config import get_settings
from asr_system.interfaces.batch.runner import BatchRunner
from asr_system.logging_config import setup_logging
from services.batch.date_context import resolve_target_date

logger = logging.getLogger(__name__)


def _upload_results_to_s3(app_settings, processing_date: date) -> None:
    """Upload output files to S3 under results/{date}/ prefix."""
    if not app_settings.s3.bucket:
        return

    import boto3

    s3 = boto3.client(
        "s3",
        aws_access_key_id=app_settings.batch_secrets.storage_access_key,
        aws_secret_access_key=app_settings.batch_secrets.storage_secret_key,
        endpoint_url=app_settings.s3.endpoint_url or None,
        region_name=app_settings.s3.region,
    )

    output_dir = Path(app_settings.storage.output_dir)
    results_prefix = f"results/{processing_date.isoformat()}"

    for filename in ("call_scores.jsonl", "utterances.jsonl"):
        local_path = output_dir / filename
        if not local_path.exists():
            continue
        s3_key = f"{results_prefix}/{filename}"
        s3.upload_file(str(local_path), app_settings.s3.bucket, s3_key)
        logger.info("Uploaded %s → s3://%s/%s", filename, app_settings.s3.bucket, s3_key)


if __name__ == "__main__":
    settings = get_settings()
    setup_logging(settings.app.log_level)
    target_date = resolve_target_date()

    processed = BatchRunner().run(target_date)
    print(f"processed_calls={len(processed)} date={target_date}")

    _upload_results_to_s3(settings, target_date)
