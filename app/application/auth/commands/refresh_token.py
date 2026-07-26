"""Use case: exchange a refresh token for a new token pair (with rotation).

The presented token is revoked and a successor is issued in the same family.
Presenting an already-revoked token is treated as replay/theft: the entire
family is revoked, ending the session chain for whoever holds any of its
tokens.
"""

from dataclasses import dataclass
from uuid import uuid4

from app.application.auth.dto import TokenPair
from app.application.shared.interfaces import Clock, TokenService, UnitOfWork
from app.domain.auth.entities import RefreshTokenRecord
from app.domain.auth.exceptions import InvalidTokenError, TokenExpiredError
from app.domain.shared.exceptions import ValidationError
from app.domain.users.value_objects import UserId


@dataclass(frozen=True, slots=True)
class RefreshTokenCommand:
    refresh_token: str


class RefreshTokenHandler:
    def __init__(
        self, uow: UnitOfWork, token_service: TokenService, clock: Clock
    ) -> None:
        self._uow = uow
        self._tokens = token_service
        self._clock = clock

    async def execute(self, command: RefreshTokenCommand) -> TokenPair:
        payload = self._tokens.decode(command.refresh_token)
        if payload.token_type != "refresh":
            raise InvalidTokenError

        record = await self._uow.refresh_tokens.get_by_jti(payload.token_id)
        if record is None:
            raise InvalidTokenError

        now = self._clock.now()
        if record.is_revoked:
            # Rotated-token replay: kill every descendant of this login.
            await self._uow.refresh_tokens.revoke_family(record.family_id, now)
            await self._uow.commit()
            raise InvalidTokenError
        if record.expires_at <= now:
            raise TokenExpiredError

        try:
            user_id = UserId.from_str(payload.subject)
        except ValidationError:
            raise InvalidTokenError from None

        user = await self._uow.users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise InvalidTokenError

        subject = str(user.id)
        record.revoke(now)
        await self._uow.refresh_tokens.update(record)

        new_jti = uuid4()
        issued = self._tokens.create_refresh_token(subject, new_jti)
        await self._uow.refresh_tokens.add(
            RefreshTokenRecord(
                jti=new_jti,
                user_id=user.id,
                family_id=record.family_id,  # successor stays in the family
                expires_at=issued.expires_at,
            )
        )
        await self._uow.commit()

        return TokenPair(
            access_token=self._tokens.create_access_token(subject),
            refresh_token=issued.token,
        )
