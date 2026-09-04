"""A workspace's ingest address, and the lookup that reverses it.

Address shape: ``<slug>-<token>@<inbound domain>``, with an optional
``+c<conversation number>`` tag on replies.

The token is random rather than derived: an address anyone could compute
from a workspace's name would let them post tickets into its queue.
"""

import re
import secrets
import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.config import get_settings
from relaydesk.errors import NotFound
from relaydesk.models.channel_account import ChannelAccount, ChannelAccountKind

TOKEN_BYTES = 6
TOKEN_PATTERN = re.compile(r"^[0-9a-f]{12}$")
_TAG = re.compile(r"\+c(\d+)$")


def new_token() -> str:
    return secrets.token_hex(TOKEN_BYTES)


def address_for(
    account: ChannelAccount, slug: str, conversation_number: int | None = None
) -> str:
    tag = f"+c{conversation_number}" if conversation_number is not None else ""
    return f"{slug}-{account.ingest_token}{tag}@{get_settings().inbound_domain}"


def _local_part(address: str) -> str:
    return (address or "").strip().lower().split("@", 1)[0]


def token_from_address(address: str) -> str | None:
    local = _TAG.sub("", _local_part(address))
    if "-" not in local:
        return None
    # Split on the last dash: workspace slugs may contain dashes, the token
    # never does.
    candidate = local.rsplit("-", 1)[-1]
    return candidate if TOKEN_PATTERN.match(candidate) else None


def conversation_number_from_address(address: str) -> int | None:
    match = _TAG.search(_local_part(address))
    return int(match.group(1)) if match else None


async def create(
    session: AsyncSession, workspace_id: uuid.UUID, display_name: str
) -> ChannelAccount:
    account = ChannelAccount(
        workspace_id=workspace_id,
        kind=ChannelAccountKind.email,
        ingest_token=new_token(),
        display_name=display_name.strip() or "Support",
        active=True,
    )
    session.add(account)
    await session.flush()
    return account


async def list_for(
    session: AsyncSession, workspace_id: uuid.UUID
) -> list[ChannelAccount]:
    result = await session.scalars(
        sa.select(ChannelAccount)
        .where(
            ChannelAccount.workspace_id == workspace_id,
            ChannelAccount.active.is_(True),
        )
        .order_by(ChannelAccount.created_at)
    )
    return list(result)


async def deactivate(
    session: AsyncSession, workspace_id: uuid.UUID, account_id: uuid.UUID
) -> None:
    account = await session.scalar(
        sa.select(ChannelAccount).where(
            ChannelAccount.id == account_id,
            ChannelAccount.workspace_id == workspace_id,
        )
    )
    if account is None:
        raise NotFound("That channel does not exist.")
    account.active = False
    await session.flush()


async def find_by_token(session: AsyncSession, token: str) -> ChannelAccount | None:
    if not token or not TOKEN_PATTERN.match(token):
        return None
    return await session.scalar(
        sa.select(ChannelAccount).where(
            ChannelAccount.ingest_token == token,
            ChannelAccount.active.is_(True),
        )
    )
