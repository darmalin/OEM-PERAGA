from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables (prefix EMS_)."""

    model_config = SettingsConfigDict(env_prefix="EMS_", extra="ignore")

    environment: Literal["dev", "test", "staging", "production"] = "dev"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://ems:ems@localhost:5432/ems"
    database_pool_size: int = 10
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"

    # Fernet key (urlsafe base64 of 32 bytes) for secrets that must be recoverable.
    app_encryption_key: SecretStr = SecretStr("")
    public_base_url: str = "http://localhost:8080"

    session_cookie_name: str = "ems_session"
    session_cookie_secure: bool = True
    session_idle_timeout_seconds: int = 2 * 60 * 60
    session_absolute_timeout_seconds: int = 12 * 60 * 60

    login_max_failures_per_account: int = 5
    login_max_attempts_per_ip: int = 30
    login_window_seconds: int = 15 * 60
    password_reset_ttl_seconds: int = 30 * 60
    password_min_length: int = 12

    public_registration_per_ip_per_hour: int = 20

    s3_endpoint_url: str | None = None
    s3_access_key: SecretStr = SecretStr("")
    s3_secret_key: SecretStr = SecretStr("")
    s3_region: str = "us-east-1"
    s3_bucket_imports: str = "imports"
    s3_bucket_exports: str = "exports"
    presigned_url_ttl_seconds: int = 300

    email_backend: Literal["smtp", "memory"] = "smtp"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: SecretStr = SecretStr("")
    smtp_use_tls: bool = False
    email_from: str = "EMS <no-reply@ems.local>"

    import_max_bytes: int = 20 * 1024 * 1024
    import_max_rows: int = 100_000
    import_batch_size: int = 500
    export_ttl_seconds: int = 24 * 60 * 60
    idempotency_ttl_seconds: int = 24 * 60 * 60

    scanner_cache_ttl_seconds: int = 12 * 60 * 60
    scanner_activation_code_ttl_seconds: int = 15 * 60

    @property
    def openapi_enabled(self) -> bool:
        return self.environment != "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
