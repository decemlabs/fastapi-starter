"""Use case: authenticate a user and issue a token pair.

Issuing a refresh token also persists a server-side record (keyed by ``jti``,
grouped into a new *family*), which is what makes rotation, reuse detection,
and revocation possible later.
"""

from dataclasses import dataclass
from uuid import uuid4

from app.application.auth.dto import TokenPair
from app.application.shared.interfaces import PasswordHasher, TokenService, UnitOfWork
from app.domain.auth.entities import RefreshTokenRecord
from app.domain.auth.exceptions import InvalidCredentialsError
from app.domain.shared.exceptions import ValidationError
from app.domain.users.value_objects import Email


@dataclass(frozen=True, slots=True)
class LoginCommand:
    email: str
    password: str


class LoginHandler:
    def __init__(
        self,
        uow: UnitOfWork,
        password_hasher: PasswordHasher,
        token_service: TokenService,
    ) -> None:
        self._uow = uow
        self._hasher = password_hasher
        self._tokens = token_service

    async def execute(self, command: LoginCommand) -> TokenPair:
        try:
            email = Email(command.email)
        except ValidationError:
            # Don't leak whether the address is even well-formed.
            raise InvalidCredentialsError from None

        user = await self._uow.users.get_by_email(email)
        if user is None or not user.is_active:
            # Hash anyway so unknown and known accounts take the same time —
            # otherwise response timing reveals which emails are registered.
            await self._hasher.hash(command.password)
            raise InvalidCredentialsError
        if not await self._hasher.verify(command.password, user.hashed_password.value):
            raise InvalidCredentialsError

        subject = str(user.id)
        jti = uuid4()
        issued = self._tokens.create_refresh_token(subject, jti)
        await self._uow.refresh_tokens.add(
            RefreshTokenRecord(
                jti=jti,
                user_id=user.id,
                family_id=uuid4(),  # a login starts a new token family
                expires_at=issued.expires_at,
            )
        )
        await self._uow.commit()

        return TokenPair(
            access_token=self._tokens.create_access_token(subject),
            refresh_token=issued.token,
        )
