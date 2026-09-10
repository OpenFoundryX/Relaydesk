from datetime import UTC, datetime, timedelta

import pytest

from relaydesk.errors import Invalid, NotFound
from relaydesk.services import widget_keys
from tests.factories import make_workspace


async def test_create_mints_a_prefixed_key(db_session):
    workspace = await make_workspace(db_session)
    created = await widget_keys.create(db_session, workspace.id, "Marketing site")

    assert created.key.startswith("rdw_")
    assert len(created.key) == 36
    assert created.allowed_origins == []


async def test_create_normalises_origins(db_session):
    workspace = await make_workspace(db_session)
    created = await widget_keys.create(
        db_session,
        workspace.id,
        "Site",
        allowed_origins=["HTTPS://ACME.COM/", "https://acme.com:443"],
    )

    # Both inputs are the same origin; it is stored once, normalised.
    assert created.allowed_origins == ["https://acme.com"]


async def test_create_refuses_an_unparseable_origin(db_session):
    workspace = await make_workspace(db_session)
    with pytest.raises(Invalid):
        await widget_keys.create(
            db_session, workspace.id, "Site", allowed_origins=["*.acme.com"]
        )


async def test_resolve_finds_an_active_key(db_session):
    workspace = await make_workspace(db_session)
    created = await widget_keys.create(db_session, workspace.id, "Site")

    found = await widget_keys.resolve(db_session, created.key)
    assert found.id == created.id


async def test_resolve_refuses_unknown_and_inactive_alike(db_session):
    """Same exception either way -- a caller must not learn which keys exist."""
    workspace = await make_workspace(db_session)
    created = await widget_keys.create(db_session, workspace.id, "Site")
    await widget_keys.update(db_session, workspace.id, created.id, active=False)

    with pytest.raises(NotFound):
        await widget_keys.resolve(db_session, created.key)
    with pytest.raises(NotFound):
        await widget_keys.resolve(db_session, "rdw_" + "0" * 32)


async def test_get_is_scoped_to_its_workspace(db_session):
    one = await make_workspace(db_session, slug="one")
    two = await make_workspace(db_session, slug="two")
    created = await widget_keys.create(db_session, one.id, "Site")

    with pytest.raises(NotFound):
        await widget_keys.get(db_session, two.id, created.id)


async def test_touch_writes_at_most_once_a_minute(db_session):
    workspace = await make_workspace(db_session)
    created = await widget_keys.create(db_session, workspace.id, "Site")

    await widget_keys.touch(db_session, created)
    first = created.last_seen_at
    assert first is not None

    await widget_keys.touch(db_session, created)
    assert created.last_seen_at == first

    created.last_seen_at = datetime.now(UTC) - timedelta(minutes=2)
    await widget_keys.touch(db_session, created)
    assert created.last_seen_at != first
