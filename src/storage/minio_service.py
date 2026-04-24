from __future__ import annotations

from datetime import datetime, timedelta
from io import BytesIO
from mimetypes import guess_type

from minio import Minio

from src.core.config import get_settings


class MinIOService:
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_root_user,
            secret_key=settings.minio_root_password,
            secure=settings.minio_secure,
            region=settings.minio_region,
        )
        self.public_client = Minio(
            endpoint=settings.minio_public_endpoint,
            access_key=settings.minio_root_user,
            secret_key=settings.minio_root_password,
            secure=settings.minio_secure,
            region=settings.minio_region,
        )

    def ensure_bucket(self, bucket: str) -> None:
        if not self.client.bucket_exists(bucket):
            self.client.make_bucket(bucket)

    def upload_bytes(
        self,
        *,
        bucket: str,
        object_name: str,
        data: bytes,
        content_type: str | None = None,
        expires_days: int | None = None,
    ) -> str:
        self.client.put_object(
            bucket_name=bucket,
            object_name=object_name,
            data=BytesIO(data),
            length=len(data),
            content_type=content_type or self._get_content_type(object_name),
        )
        return self.get_presigned_url(
            bucket=bucket,
            object_name=object_name,
            expires_days=expires_days,
        )

    def download_bytes(self, *, bucket: str, object_name: str) -> bytes:
        response = self.client.get_object(bucket_name=bucket, object_name=object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def delete_objects_older_than(self, *, bucket: str, older_than: datetime) -> int:
        deleted = 0
        objects = self.client.list_objects(bucket_name=bucket, recursive=True)
        for obj in objects:
            if obj.object_name is None or obj.last_modified is None:
                continue
            if obj.last_modified < older_than:
                self.client.remove_object(bucket_name=bucket, object_name=obj.object_name)
                deleted += 1
        return deleted

    def get_presigned_url(
        self,
        *,
        bucket: str,
        object_name: str,
        expires_days: int | None = None,
    ) -> str:
        expires = timedelta(days=expires_days or self.settings.minio_presigned_expires_days)
        return self.public_client.presigned_get_object(
            bucket_name=bucket,
            object_name=object_name,
            expires=expires,
        )

    def _get_content_type(self, object_name: str) -> str:
        content_type, _ = guess_type(object_name)
        return content_type or "application/octet-stream"
