"""The production-configuration guard must reject unsafe settings at boot."""

import pytest
from pydantic import SecretStr, ValidationError
from pydantic_settings import SettingsConfigDict

from app.core.config import AppSettings, Environment, JwtSettings, Settings

STRONG_SECRET = "a" * 40


class EnvFreeSettings(Settings):
    """Settings that ignore any local ``.env`` file, for deterministic tests."""

    model_config = SettingsConfigDict(
        env_file=None,
        env_nested_delimiter="__",
        extra="ignore",
    )


def _production_settings(
    app: AppSettings | None = None,
    jwt: JwtSettings | None = None,
) -> Settings:
    return EnvFreeSettings(
        environment=Environment.PRODUCTION,
        app=app if app is not None else AppSettings(debug=False),
        jwt=jwt if jwt is not None else JwtSettings(secret=SecretStr(STRONG_SECRET)),
    )


def test_production_accepts_safe_configuration() -> None:
    settings = _production_settings()
    assert settings.is_production


def test_production_rejects_default_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="insecure default"):
        _production_settings(jwt=JwtSettings())


def test_production_rejects_short_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="shorter than 32 bytes"):
        _production_settings(jwt=JwtSettings(secret=SecretStr("short")))


def test_production_rejects_debug_mode() -> None:
    with pytest.raises(ValidationError, match="APP__DEBUG"):
        _production_settings(app=AppSettings(debug=True))


def test_production_rejects_wildcard_cors() -> None:
    with pytest.raises(ValidationError, match="wildcard"):
        _production_settings(app=AppSettings(cors_origins=["*"]))


def test_non_production_accepts_defaults() -> None:
    settings = EnvFreeSettings(environment=Environment.LOCAL)
    assert not settings.is_production
