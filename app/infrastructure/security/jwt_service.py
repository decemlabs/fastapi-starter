"""JWT token service backed by PyJWT.

Signing and verification are delegated to PyJWT — we never hand-roll JWT
parsing or signature checks. The decoded payload is validated into a typed
:class:`TokenPayload` (no ``Any`` escapes this boundary).
"""

from datetime import timedelta
from typing import Final

import jwt

from app.application.shared.interfaces import Clock, TokenPayload, TokenType
from app.core.config import JwtSettings
from app.domain.auth.exceptions import InvalidTokenError

_ACCESS: Final[TokenType] = "access"
_REFRESH: Final[TokenType] = "refresh"


class JwtTokenService:
    """Implements the TokenService port using PyJWT."""

    def __init__(self, settings: JwtSettings, clock: Clock) -> None:
        self._settings = settings
        self._clock = clock

    def create_access_token(self, subject: str) -> str:
        return self._encode(
            subject,
            _ACCESS,
            timedelta(minutes=self._settings.access_token_expire_minutes),
        )

    def create_refresh_token(self, subject: str) -> str:
        return self._encode(
            subject,
            _REFRESH,
            timedelta(days=self._settings.refresh_token_expire_days),
        )

    def decode(self, token: str) -> TokenPayload:
        try:
            raw: dict[str, object] = jwt.decode(
                token,
                self._settings.secret.get_secret_value(),
                algorithms=[self._settings.algorithm],
            )
        except jwt.PyJWTError as exc:
            raise InvalidTokenError from exc

        subject = raw.get("sub")
        token_type = raw.get("type")
        if not isinstance(subject, str):
            raise InvalidTokenError
        # Compare against the known literals and pass them through directly, so
        # `token_type` is provably a TokenType without any cast or narrowing.
        if token_type == "access":
            return TokenPayload(subject=subject, token_type="access")
        if token_type == "refresh":
            return TokenPayload(subject=subject, token_type="refresh")
        raise InvalidTokenError

    def _encode(self, subject: str, token_type: TokenType, lifetime: timedelta) -> str:
        now = self._clock.now()
        payload: dict[str, str | int] = {
            "sub": subject,
            "type": token_type,
            "iat": int(now.timestamp()),
            "exp": int((now + lifetime).timestamp()),
        }
        return jwt.encode(
            payload,
            self._settings.secret.get_secret_value(),
            algorithm=self._settings.algorithm,
        )
