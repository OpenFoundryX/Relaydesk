from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa

from relaydesk.errors import NotFound, Unauthorized
from relaydesk.models import ApiKey, ApiKeyScope
from relaydesk.security.tokens import hash_token
from relaydesk.services import api_keys
from tests.factories import make_member, make_workspace


async def _mint(db_session, workspace, user=None, **kwargs):
    return await api_keys.mint(
        db_session,
        workspace.id,
        name=kwargs.pop("name", "Production ingest"),
        scopes=kwargs.pop("scopes", [ApiKeyScope.conversations_read]),
        created_by_user_id=user.id if user else None,
        **kwargs,
    )


async def test_mint_returns_a_prefixed_token_and_stores_only_its_hash(
    db_session,
) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)

    token, key = await _mint(db_session, workspace, user)

    assert token.startswith("rd_")
    assert key.token_hash == hash_token(token)
    assert token not in (key.prefix, key.token_hash)
    # The prefix is "rd_" plus four characters of the secret.
    assert key.prefix == token[:7]
    assert key.scopes == ["conversations:read"]
    assert key.created_by_user_id == user.id


async def test_two_mints_never_produce_the_same_token(db_session) -> None:
    workspace = await make_workspace(db_session)

    first, _ = await _mint(db_session, workspace, name="One")
    second, _ = await _mint(db_session, workspace, name="Two")

    assert first != second


async def test_resolve_finds_a_live_key(db_session) -> None:
    workspace = await make_workspace(db_session)
    token, key = await _mint(db_session, workspace)

    resolved = await api_keys.resolve(db_session, token)

    assert resolved.id == key.id


async def test_resolve_refuses_an_unknown_token(db_session) -> None:
    with pytest.raises(Unauthorized):
        await api_keys.resolve(db_session, "rd_nothing-was-ever-minted-here")


async def test_resolve_refuses_a_revoked_key(db_session) -> None:
    workspace = await make_workspace(db_session)
    token, key = await _mint(db_session, workspace)
    key.revoked_at = datetime.now(UTC)
    await db_session.commit()

    with pytest.raises(Unauthorized):
        await api_keys.resolve(db_session, token)


async def test_resolve_refuses_an_expired_key(db_session) -> None:
    workspace = await make_workspace(db_session)
    token, key = await _mint(
        db_session, workspace, expires_at=datetime.now(UTC) - timedelta(seconds=1)
    )

    with pytest.raises(Unauthorized):
        await api_keys.resolve(db_session, token)


async def test_resolve_stamps_last_used_once_per_interval(db_session) -> None:
    workspace = await make_workspace(db_session)
    token, key = await _mint(db_session, workspace)

    await api_keys.resolve(db_session, token)
    first = (
        await db_session.scalar(sa.select(ApiKey).where(ApiKey.id == key.id))
    ).last_used_at
    assert first is not None

    await api_keys.resolve(db_session, token)
    second = (
        await db_session.scalar(sa.select(ApiKey).where(ApiKey.id == key.id))
    ).last_used_at
    assert second == first

    key.last_used_at = datetime.now(UTC) - api_keys.LAST_USED_INTERVAL * 2
    await db_session.commit()
    await api_keys.resolve(db_session, token)
    third = (
        await db_session.scalar(sa.select(ApiKey).where(ApiKey.id == key.id))
    ).last_used_at
    assert third > first


async def test_list_keys_returns_only_this_workspaces_keys(db_session) -> None:
    ours = await make_workspace(db_session, slug="ours")
    theirs = await make_workspace(db_session, slug="theirs")
    await _mint(db_session, ours, name="Ours")
    await _mint(db_session, theirs, name="Theirs")

    rows = await api_keys.list_keys(db_session, ours.id)

    assert [row.name for row in rows] == ["Ours"]


async def test_revoke_marks_the_row_rather_than_deleting_it(db_session) -> None:
    workspace = await make_workspace(db_session)
    _, key = await _mint(db_session, workspace)

    await api_keys.revoke(db_session, workspace.id, key.id)

    stored = await db_session.scalar(sa.select(ApiKey).where(ApiKey.id == key.id))
    assert stored is not None
    assert stored.revoked_at is not None


async def test_revoke_cannot_reach_another_workspaces_key(db_session) -> None:
    ours = await make_workspace(db_session, slug="ours")
    theirs = await make_workspace(db_session, slug="theirs")
    _, key = await _mint(db_session, theirs)

    with pytest.raises(NotFound):
        await api_keys.revoke(db_session, ours.id, key.id)


async def test_mint_refuses_a_scope_outside_the_closed_set(db_session) -> None:
    workspace = await make_workspace(db_session)

    with pytest.raises(ValueError):
        await api_keys.mint(
            db_session,
            workspace.id,
            name="Bad",
            scopes=["workspace:destroy"],
            created_by_user_id=None,
        )
