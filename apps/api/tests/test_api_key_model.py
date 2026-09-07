from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from relaydesk.models import ApiKey, ApiKeyScope
from tests.factories import make_member, make_workspace


async def test_a_key_round_trips_its_scopes(db_session) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    key = ApiKey(
        workspace_id=workspace.id,
        name="Production ingest",
        prefix="rd_7f2a",
        token_hash="a" * 64,
        scopes=[
            ApiKeyScope.conversations_read.value,
            ApiKeyScope.messages_write.value,
        ],
        created_by_user_id=user.id,
    )
    db_session.add(key)
    await db_session.commit()

    stored = await db_session.scalar(sa.select(ApiKey).where(ApiKey.id == key.id))

    assert stored.scopes == ["conversations:read", "messages:write"]
    assert stored.revoked_at is None
    assert stored.expires_at is None
    assert stored.last_used_at is None


async def test_two_keys_cannot_share_a_token_hash(db_session) -> None:
    workspace = await make_workspace(db_session)
    db_session.add(
        ApiKey(
            workspace_id=workspace.id,
            name="First",
            prefix="rd_1111",
            token_hash="b" * 64,
            scopes=[],
        )
    )
    await db_session.commit()

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(
                ApiKey(
                    workspace_id=workspace.id,
                    name="Second",
                    prefix="rd_2222",
                    token_hash="b" * 64,
                    scopes=[],
                )
            )
            await db_session.flush()


async def test_an_expiry_is_stored_with_its_offset(db_session) -> None:
    workspace = await make_workspace(db_session)
    expires = datetime.now(UTC) + timedelta(days=30)
    key = ApiKey(
        workspace_id=workspace.id,
        name="Temporary",
        prefix="rd_3333",
        token_hash="c" * 64,
        scopes=[ApiKeyScope.conversations_read.value],
        expires_at=expires,
    )
    db_session.add(key)
    await db_session.commit()

    stored = await db_session.scalar(sa.select(ApiKey).where(ApiKey.id == key.id))

    assert stored.expires_at.tzinfo is not None
    assert abs((stored.expires_at - expires).total_seconds()) < 1


def test_the_scope_set_is_exactly_the_six_the_spec_names() -> None:
    assert {scope.value for scope in ApiKeyScope} == {
        "conversations:read",
        "conversations:write",
        "messages:write",
        "contacts:read",
        "labels:read",
        "labels:write",
    }
