from __future__ import annotations

from datetime import timedelta
from io import BytesIO
from mimetypes import guess_type
from urllib.parse import urlsplit, urlunsplit

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

    def get_presigned_url(
        self,
        *,
        bucket: str,
        object_name: str,
        expires_days: int | None = None,
    ) -> str:
        expires = timedelta(days=expires_days or self.settings.minio_presigned_expires_days)
        url = self.client.presigned_get_object(
            bucket_name=bucket,
            object_name=object_name,
            expires=expires,
        )
        return self._to_public_url(url)

    def _get_content_type(self, object_name: str) -> str:
        content_type, _ = guess_type(object_name)
        return content_type or "application/octet-stream"

    def _to_public_url(self, url: str) -> str:
        parsed = urlsplit(url)
        scheme = "https" if self.settings.minio_secure else "http"
        return urlunsplit(
            (
                scheme,
                self.settings.minio_public_endpoint,
                parsed.path,
                parsed.query,
                parsed.fragment,
            )
        )
