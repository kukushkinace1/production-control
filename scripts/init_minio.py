from __future__ import annotations

import time

from minio.error import S3Error

from src.core.config import get_settings
from src.storage import MinIOService


def initialize_minio_buckets() -> None:
    settings = get_settings()
    service = MinIOService()
    buckets = [
        settings.minio_reports_bucket,
        settings.minio_exports_bucket,
        settings.minio_imports_bucket,
    ]
    for bucket_name in buckets:
        service.ensure_bucket(bucket_name)
        print(f"Created or verified bucket: {bucket_name}")


if __name__ == "__main__":
    for attempt in range(10):
        try:
            initialize_minio_buckets()
            break
        except S3Error:
            if attempt == 9:
                raise
            time.sleep(2)
