"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:3000"
    # Override in every real deploy. Default exists so local CI/scaffold can boot.
    session_secret: str = Field(
        default="local-dev-only-change-me-32chars",
        min_length=16,
    )
    session_cookie_name: str = "databuddy_session"
    environment: str = "local"
    log_level: str = "INFO"

    # Table owner / migrator (CREATE TABLE, Alembic). Not used for student HTTP.
    database_url: str = (
        "postgresql+psycopg://databuddy:databuddy@localhost:5432/databuddy"
    )
    # FastAPI request role: RLS forced, no BYPASSRLS.
    database_app_url: str = (
        "postgresql+psycopg://databuddy_app:databuddy_app@localhost:5432/databuddy"
    )
    # Platform-admin role only: BYPASSRLS. Never for student traffic.
    database_admin_url: str = (
        "postgresql+psycopg://databuddy_admin:databuddy_admin@localhost:5432/databuddy"
    )

    # "s3" for MinIO/R2; "local" writes under local_storage_path (no Docker needed).
    storage_backend: str = "local"
    local_storage_path: str = ".data/objects"
    s3_endpoint_url: str | None = "http://localhost:9000"
    s3_region: str = "us-east-1"
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin"
    s3_bucket: str = "databuddy"
    s3_public_endpoint_url: str | None = "http://localhost:9000"
    s3_force_path_style: bool = True
    # Signed GET URLs are short-lived; bucket stays private.
    s3_presign_ttl_seconds: int = 300
    # Hard upload cap (bytes). Enforced while reading the request body.
    max_upload_bytes: int = 500 * 1024 * 1024

    google_client_id: str = ""
    google_client_secret: str = ""
    # Prefer the Next.js origin so the session cookie is set same-site as the app.
    google_redirect_uri: str = "http://localhost:3000/api/auth/google/callback"

    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_tenant_id: str = "common"
    microsoft_redirect_uri: str = (
        "http://localhost:3000/api/auth/microsoft/callback"
    )

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-20260514"
    user_token_budget_usd: float = 50.0
    enforce_institution_budget: bool = False
    institution_token_budget_usd: float = 250.0

    e2b_api_key: str = ""
    e2b_template_id: str = "databuddy-sandbox"
    e2b_timeout_seconds: int = 120
    e2b_allow_internet_access: bool = False

    # Optional SMTP. When unset, invites are written to local_storage outbox + logs.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "DataBuddy <noreply@localhost>"
    smtp_use_tls: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)


@lru_cache
def get_settings() -> Settings:
    return Settings()
