import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import NotFound, Unauthorized
from relaydesk.models import ApiKey, ApiKeyScope
from relaydesk.security.tokens import generate_token, hash_token

# Mirrors ``services.auth.LAST_SEEN_INTERVAL`` and exists for the same
# reason: the only consumer of ``last_used_at`` is a "Last used" label in a
# settings list, and writing it on every request would put a write on the
# hot path of every read.
LAST_USED_INTERVAL = timedelta(hours=1)

# Uniform on purpose. A caller must not be able to tell an unknown token from
# a revoked one from an expired one -- the difference is only useful to
# somebody probing with tokens that are not theirs.
BAD_KEY = "API key is invalid, revoked or expired."


def _new_token() -> tuple[str, str]:
    """A fresh token and the prefix stored beside its hash.

    The prefix is ``rd_`` plus the first four characters of the secret. It is
    shown in the console so a human can tell two keys apart. Four characters
    of a 43-character token narrow nothing: an attacker who could brute-force
    the remaining 39 could brute-force all 43.
    """
    token = f"rd_{generate_token()}"
    return token, token[:7]


async def mint(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    name: str,
    scopes: Sequence[ApiKeyScope | str],
    created_by_user_id: uuid.UUID | None,
    expires_at: datetime | None = None,
) -> tuple[str, ApiKey]:
    """Create a key and return its plaintext token exactly once.

    The returned token is never recoverable afterwards: only its SHA-256
    digest is stored. SHA-256 rather than argon2 for the same reason
    ``Session`` uses it -- the token is 256 bits of CSPRNG output with no
    low-entropy structure, so there is no dictionary to slow down, and a
    password KDF on the hot path of every API request would only buy latency.

    This is the only writer of ``ApiKey.scopes``, so it is where the closed
    set is enforced (see the note on the column: an array column cannot carry
    the CHECK-constraint pattern the scalar enum columns use).
    """
    trimmed = name.strip()
    if not trimmed:
        raise ValueError("An API key needs a name.")

    values = [ApiKeyScope(scope).value for scope in scopes]

    token, prefix = _new_token()
    key = ApiKey(
        workspace_id=workspace_id,
        name=trimmed[:120],
        prefix=prefix,
        token_hash=hash_token(token),
        scopes=values,
        created_by_user_id=created_by_user_id,
        expires_at=expires_at,
    )
    session.add(key)
    await session.commit()
    return token, key


async def resolve(session: AsyncSession, token: str) -> ApiKey:
    """The live key a bearer token names, or ``Unauthorized``.

    A single unique-index lookup on the digest, so there is no per-candidate
    comparison and no timing channel of the kind ``services.auth.authenticate``
    guards against.
    """
    key = await session.scalar(
        sa.select(ApiKey).where(ApiKey.token_hash == hash_token(token))
    )
    if key is None or key.revoked_at is not None:
        raise Unauthorized(BAD_KEY)

    now = datetime.now(UTC)
    if key.expires_at is not None and key.expires_at <= now:
        raise Unauthorized(BAD_KEY)

    if key.last_used_at is None or now - key.last_used_at > LAST_USED_INTERVAL:
        key.last_used_at = now
        await session.commit()
    return key


async def list_keys(session: AsyncSession, workspace_id: uuid.UUID) -> list[ApiKey]:
    """Live keys, newest first. Revoked rows are kept for attribution but are
    not offered back to the console as though they still worked."""
    return list(
        await session.scalars(
            sa.select(ApiKey)
            .where(ApiKey.workspace_id == workspace_id, ApiKey.revoked_at.is_(None))
            .order_by(ApiKey.created_at.desc(), ApiKey.id.desc())
        )
    )


async def revoke(
    session: AsyncSession, workspace_id: uuid.UUID, key_id: uuid.UUID
) -> None:
    """Stop a key working, keeping its row.

    Scoped by workspace, and a key belonging to another workspace raises
    ``NotFound`` rather than ``Forbidden`` -- the slice-1 isolation contract.
    """
    key = await session.scalar(
        sa.select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.workspace_id == workspace_id,
            ApiKey.revoked_at.is_(None),
        )
    )
    if key is None:
        raise NotFound("API key not found.")
    key.revoked_at = datetime.now(UTC)
    await session.commit()
