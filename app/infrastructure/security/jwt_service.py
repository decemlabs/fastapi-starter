"""JWT token service backed by PyJWT.

Signing and verification are delegated to PyJWT — we never hand-roll JWT
parsing or signature checks. Claims (``iss``, ``aud``, ``exp``, ``jti``) are
enforced through PyJWT's own validation options. The decoded payload is
validated into a typed :class:`TokenPayload` (no ``Any`` escapes this
boundary).
"""

from datetime import timedelta
from typing import Final
from uuid import UUID, uuid4

import jwt

from app.application.shared.interfaces import (
    Clock,
    IssuedToken,
    TokenPayload,
    TokenType,
)
from app.core.config import JwtSettings
from app.domain.auth.exceptions import InvalidTokenError, TokenExpiredError

_ACCESS: Final[TokenType] = "access"
_REFRESH: Final[TokenType] = "refresh"
_REQUIRED_CLAIMS: Final = ["sub", "type", "iat", "exp", "jti", "iss", "aud"]


class JwtTokenService:
    """Implements the TokenService port using PyJWT."""

    def __init__(self, settings: JwtSettings, clock: Clock) -> None:
        self._settings = settings
        self._clock = clock

    def create_access_token(self, subject: str) -> str:
        return self._encode(
            subject,
            _ACCESS,
            uuid4(),
            timedelta(minutes=self._settings.access_token_expire_minutes),
        ).token

    def create_refresh_token(self, subject: str, token_id: UUID) -> IssuedToken:
        return self._encode(
            subject,
            _REFRESH,
            token_id,
            timedelta(days=self._settings.refresh_token_expire_days),
        )

    def decode(self, token: str) -> TokenPayload:
        try:
            raw: dict[str, object] = jwt.decode(
                token,
                self._settings.secret.get_secret_value(),
                algorithms=[self._settings.algorithm],
                issuer=self._settings.issuer,
                audience=self._settings.audience,
                options={"require": _REQUIRED_CLAIMS},
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenExpiredError from exc
        except jwt.PyJWTError as exc:
            raise InvalidTokenError from exc

        subject = raw.get("sub")
        token_type = raw.get("type")
        jti = raw.get("jti")
        if not isinstance(subject, str) or not isinstance(jti, str):
            raise InvalidTokenError
        try:
            token_id = UUID(jti)
        except ValueError as exc:
            raise InvalidTokenError from exc
        # Compare against the known literals and pass them through directly, so
        # `token_type` is provably a TokenType without any cast or narrowing.
        if token_type == "access":
            return TokenPayload(subject=subject, token_type="access", token_id=token_id)
        if token_type == "refresh":
            return TokenPayload(
                subject=subject, token_type="refresh", token_id=token_id
            )
        raise InvalidTokenError

    def _encode(
        self,
        subject: str,
        token_type: TokenType,
        token_id: UUID,
        lifetime: timedelta,
    ) -> IssuedToken:
        now = self._clock.now()
        expires_at = now + lifetime
        payload: dict[str, str | int] = {
            "sub": subject,
            "type": token_type,
            "jti": str(token_id),
            "iss": self._settings.issuer,
            "aud": self._settings.audience,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        token = jwt.encode(
            payload,
            self._settings.secret.get_secret_value(),
            algorithm=self._settings.algorithm,
        )
        return IssuedToken(token=token, expires_at=expires_at)
