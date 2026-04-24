from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Production Control API"
    app_version: str = "0.1.0"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: str = "false"

    postgres_db: str = "production_control"
    postgres_user: str = "production_control"
    postgres_password: str = "production_control"
    postgres_host: str = "postgres"
    postgres_port: int = 5433
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    rabbitmq_default_user: str = "production_control"
    rabbitmq_default_pass: str = "production_control"
    rabbitmq_host: str = "rabbitmq"
    rabbitmq_port: int = 5672
    celery_task_serializer: str = "json"
    celery_result_serializer: str = "json"
    celery_accept_content: str = "json"
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "minioadmin"
    minio_host: str = "localhost"
    minio_port: int = 9000
    minio_secure: bool = False
    minio_public_host: str = "localhost"
    minio_public_port: int = 9000
    minio_region: str = "us-east-1"
    minio_reports_bucket: str = "reports"
    minio_exports_bucket: str = "exports"
    minio_imports_bucket: str = "imports"
    minio_presigned_expires_days: int = 7

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @computed_field
    @property
    def database_url(self) -> str:
        return (
            "postgresql+asyncpg://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field
    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @computed_field
    @property
    def rabbitmq_url(self) -> str:
        return (
            "amqp://"
            f"{self.rabbitmq_default_user}:{self.rabbitmq_default_pass}"
            f"@{self.rabbitmq_host}:{self.rabbitmq_port}//"
        )

    @computed_field
    @property
    def minio_endpoint(self) -> str:
        return f"{self.minio_host}:{self.minio_port}"

    @computed_field
    @property
    def minio_public_endpoint(self) -> str:
        return f"{self.minio_public_host}:{self.minio_public_port}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
