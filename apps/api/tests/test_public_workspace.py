import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Invalid
from relaydesk.services import workspaces
from tests.factories import make_workspace


async def test_the_public_endpoint_returns_display_information(
    db_session, client
) -> None:
    await make_workspace(db_session, slug="acme")
    await db_session.commit()

    response = await client.get("/api/public/workspaces/acme")

    assert response.status_code == 200
    assert set(response.json()) == {"name", "monogram"}


async def test_the_public_endpoint_needs_no_session(db_session, client) -> None:
    """The whole point is that acme.<portal domain> is reachable by anyone."""
    await make_workspace(db_session, slug="acme")
    await db_session.commit()

    response = await client.get("/api/public/workspaces/acme")

    assert response.status_code == 200


async def test_an_unknown_slug_is_a_404(db_session, client) -> None:
    response = await client.get("/api/public/workspaces/nobody")

    assert response.status_code == 404


async def test_the_endpoint_leaks_nothing_beyond_display_fields(
    db_session, client
) -> None:
    """It is public, so it must not carry plan, seat counts, ticket volume, or
    anything else a competitor could scrape."""
    await make_workspace(db_session, slug="acme")
    await db_session.commit()

    body = await client.get("/api/public/workspaces/acme")

    for leaked in ("plan", "conversationSeq", "ticketsThisPeriod", "timezone", "id"):
        assert leaked not in body.json()


@pytest.mark.parametrize("slug", ["www", "app", "api", "admin", "mail", "inbound"])
async def test_a_reserved_label_cannot_be_registered_as_a_slug(
    db_session: AsyncSession, slug: str
) -> None:
    """Otherwise registering `api` takes over a hostname the deployment needs."""
    with pytest.raises(Invalid):
        await workspaces.create_workspace(
            db_session, name="Nope", slug=slug, monogram="NO"
        )


async def test_a_reserved_label_is_a_404_on_the_public_endpoint(
    db_session, client
) -> None:
    response = await client.get("/api/public/workspaces/api")

    assert response.status_code == 404
