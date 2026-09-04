import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import NotFound
from relaydesk.services import channel_accounts
from tests.factories import make_member, make_workspace, sign_in


async def test_an_address_is_slug_then_token(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session, slug="acme")
    account = await channel_accounts.create(db_session, workspace.id, "Support")

    address = channel_accounts.address_for(account, "acme")

    assert address == f"acme-{account.ingest_token}@inbound.localhost"


def test_a_reply_address_carries_the_conversation_number() -> None:
    address = "acme-a3f9c2b1d4e5+c142@inbound.localhost"

    assert channel_accounts.token_from_address(address) == "a3f9c2b1d4e5"
    assert channel_accounts.conversation_number_from_address(address) == 142


def test_a_plain_address_has_no_conversation_number() -> None:
    address = "acme-a3f9c2b1d4e5@inbound.localhost"

    assert channel_accounts.token_from_address(address) == "a3f9c2b1d4e5"
    assert channel_accounts.conversation_number_from_address(address) is None


def test_a_slug_containing_dashes_still_resolves() -> None:
    """Split on the last dash, not the first: workspace slugs contain them."""
    address = "acme-support-eu-a3f9c2b1d4e5@inbound.localhost"

    assert channel_accounts.token_from_address(address) == "a3f9c2b1d4e5"


def test_an_unrelated_address_yields_no_token() -> None:
    assert channel_accounts.token_from_address("support@acme.com") is None
    assert channel_accounts.token_from_address("") is None


async def test_tokens_are_not_derived_from_the_slug(db_session: AsyncSession) -> None:
    """A derivable address would let anyone who can guess a workspace name
    post tickets into its queue."""
    first = await make_workspace(db_session, slug="acme")
    second = await make_workspace(db_session, slug="acme-two")
    one = await channel_accounts.create(db_session, first.id, "Support")
    two = await channel_accounts.create(db_session, second.id, "Support")

    assert one.ingest_token != two.ingest_token
    assert len(one.ingest_token) == 12
    assert "acme" not in one.ingest_token


async def test_lookup_by_token_finds_the_workspace(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session, slug="acme")
    account = await channel_accounts.create(db_session, workspace.id, "Support")

    found = await channel_accounts.find_by_token(db_session, account.ingest_token)

    assert found is not None
    assert found.workspace_id == workspace.id


async def test_a_deactivated_account_is_not_found(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session, slug="acme")
    account = await channel_accounts.create(db_session, workspace.id, "Support")
    await channel_accounts.deactivate(db_session, workspace.id, account.id)

    found = await channel_accounts.find_by_token(db_session, account.ingest_token)
    assert found is None


async def test_another_workspace_cannot_deactivate_your_account(
    db_session: AsyncSession,
) -> None:
    mine = await make_workspace(db_session, slug="acme")
    theirs = await make_workspace(db_session, slug="other")
    account = await channel_accounts.create(db_session, mine.id, "Support")

    with pytest.raises(NotFound):
        await channel_accounts.deactivate(db_session, theirs.id, account.id)


async def test_the_channels_route_lists_addresses(db_session, client) -> None:
    workspace = await make_workspace(db_session, slug="acme")
    member = await make_member(db_session, workspace, email="nilesh@example.com")
    await channel_accounts.create(db_session, workspace.id, "Support")
    await db_session.commit()
    headers = await sign_in(client, db_session, member.email)

    response = await client.get("/api/channels/email", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["address"].endswith("@inbound.localhost")
    assert body[0]["displayName"] == "Support"


async def test_creating_a_channel_requires_admin(db_session, client) -> None:
    from relaydesk.models.membership import Role

    workspace = await make_workspace(db_session, slug="acme")
    agent = await make_member(
        db_session, workspace, email="sara@example.com", role=Role.agent
    )
    await db_session.commit()
    headers = await sign_in(client, db_session, agent.email)

    response = await client.post(
        "/api/channels/email", json={"displayName": "Billing"}, headers=headers
    )

    assert response.status_code == 403
