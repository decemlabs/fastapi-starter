"""Argon2 password hashing via pwdlib.

We use a maintained hashing library (pwdlib, Argon2 backend) rather than
hand-rolling anything. Passwords are never stored in plaintext.

Argon2 is CPU-bound by design, so both operations run in a worker thread via
``anyio.to_thread`` — a synchronous call here would stall the entire event
loop for tens of milliseconds per login.
"""

import anyio.to_thread
from pwdlib import PasswordHash


class PwdlibPasswordHasher:
    """Implements the PasswordHasher port using pwdlib's recommended (Argon2) hasher."""

    def __init__(self) -> None:
        self._hasher = PasswordHash.recommended()

    async def hash(self, plain_password: str) -> str:
        return await anyio.to_thread.run_sync(self._hasher.hash, plain_password)

    async def verify(self, plain_password: str, hashed_password: str) -> bool:
        return await anyio.to_thread.run_sync(
            self._hasher.verify, plain_password, hashed_password
        )
