"""Typed application configuration via pydantic-settings.

Settings come from environment variables (and an optional ``.env`` file).
Nested settings use a double-underscore delimiter, e.g. ``DATABASE__URL``.
Grouping related settings into sub-models keeps the surface organised as the
project grows (``settings.database.url`` rather than a flat ``database_url``).

``Settings`` fails fast on unsafe production configuration: a default or weak
JWT secret, debug mode, or wildcard CORS abort startup instead of booting a
vulnerable service.
"""

from enum import StrEnum
from functools import lru_cache
from typing import Literal, Self

from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_JWT_SECRET = "change-me-in-production"
_MIN_JWT_SECRET_BYTES = 32


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class AppSettings(BaseModel):
    name: str = "fastapi-starter"
    debug: bool = False
    cors_origins: list[str] = Field(default_factory=list)
    # Host-header allow-list (TrustedHostMiddleware). The wildcard default is
    # for local development; production requires explicit hosts.
    allowed_hosts: list[str] = Field(default_factory=lambda: ["*"])
    max_request_body_bytes: int = 1_048_576  # 1 MiB


class DatabaseSettings(BaseModel):
    url: SecretStr = SecretStr(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/app"
    )
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10


class JwtSettings(BaseModel):
    secret: SecretStr = SecretStr(_INSECURE_JWT_SECRET)
    # Literal, not str: an algorithm like "none" is unrepresentable.
    algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    # iss/aud claims, validated on decode. Part of the project-rename checklist.
    issuer: str = "fastapi-starter"
    audience: str = "fastapi-starter"


class RedisSettings(BaseModel):
    url: SecretStr = SecretStr("redis://localhost:6379/0")


class RateLimitSettings(BaseModel):
    # Applies to the public auth endpoints (login/register), per client IP.
    auth_requests: int = 10
    auth_window_seconds: int = 60


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    environment: Environment = Environment.LOCAL
    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    jwt: JwtSettings = Field(default_factory=JwtSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION

    @model_validator(mode="after")
    def _reject_unsafe_production_config(self) -> Self:
        if not self.is_production:
            return self
        problems: list[str] = []
        secret = self.jwt.secret.get_secret_value()
        if secret == _INSECURE_JWT_SECRET:
            problems.append("JWT__SECRET is still the insecure default")
        elif len(secret.encode()) < _MIN_JWT_SECRET_BYTES:
            problems.append(
                f"JWT__SECRET is shorter than {_MIN_JWT_SECRET_BYTES} bytes"
            )
        if self.app.debug:
            problems.append("APP__DEBUG must be false in production")
        if "*" in self.app.cors_origins:
            problems.append("APP__CORS_ORIGINS must not contain a wildcard")
        if "*" in self.app.allowed_hosts:
            problems.append("APP__ALLOWED_HOSTS must list explicit hosts")
        if problems:
            raise ValueError("unsafe production configuration: " + "; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    """Cached accessor used as the composition-root entry point."""
    return Settings()
