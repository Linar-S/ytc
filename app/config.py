"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the application.

    Defaults are intentionally non-secret so the package can be imported
    locally without a .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    # Application
    app_name: str = "YouTube Copy"
    app_env: str = Field(
        default="development",
        validation_alias=AliasChoices("ENVIRONMENT", "APP_ENV"),
    )
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    max_video_size_bytes: int = Field(
        default=2 * 1024**3,
        validation_alias=AliasChoices("MAX_VIDEO_SIZE_BYTES", "MAX_UPLOAD_SIZE_BYTES"),
    )
    upload_url_ttl_seconds: int = Field(
        default=3600,
        validation_alias=AliasChoices("UPLOAD_URL_TTL_SECONDS", "PRESIGNED_URL_TTL_SECONDS"),
    )

    playback_url_ttl_seconds: int = Field(
        default=6 * 3600,
        validation_alias=AliasChoices("PLAYBACK_URL_TTL_SECONDS", "VIDEO_URL_TTL_SECONDS"),
    )

    # JWT. The aliases match the deployment-facing names in .env.example.
    jwt_secret_key: str = Field(
        default="",
        validation_alias=AliasChoices("JWT_SECRET_KEY", "SECRET_KEY"),
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = Field(
        default=15,
        validation_alias=AliasChoices(
            "ACCESS_TOKEN_EXPIRE_MINUTES",
            "JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
        ),
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7,
        validation_alias=AliasChoices(
            "REFRESH_TOKEN_EXPIRE_DAYS",
            "JWT_REFRESH_TOKEN_EXPIRE_DAYS",
        ),
    )

    # Infrastructure
    database_url: str = "postgresql+asyncpg://postgres@localhost:5432/youtube_copy"
    redis_url: str = "redis://localhost:6379/0"
    minio_endpoint: str = "localhost:9000"
    minio_public_endpoint: str = Field(
        default="localhost:9000",
        validation_alias=AliasChoices("MINIO_PUBLIC_ENDPOINT", "MINIO_EXTERNAL_ENDPOINT"),
    )
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_secure: bool = False
    minio_bucket: str = "youtube"

    # CORS
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:8000",
        ]
    )
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = Field(default_factory=lambda: ["*"])
    cors_allow_headers: list[str] = Field(default_factory=lambda: ["*"])

    @property
    def secret_key(self) -> str:
        """JWT signing secret under the conventional ``settings.secret_key`` name."""

        return self.jwt_secret_key

    @property
    def access_token_expire_minutes(self) -> int:
        """Convenience alias for JWT access-token lifetime."""

        return self.jwt_access_token_expire_minutes

    @property
    def refresh_token_expire_days(self) -> int:
        """Convenience alias for JWT refresh-token lifetime."""

        return self.jwt_refresh_token_expire_days


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()


settings = get_settings()
