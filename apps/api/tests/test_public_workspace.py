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
    """With nothing in the database, a 404 proves nothing -- a real tenant
    has to exist for "correctly refused" to be distinguishable from "there
    was nothing to find"."""
    other = await make_workspace(db_session, slug="acme")
    await db_session.commit()

    response = await client.get("/api/public/workspaces/nobody")

    assert response.status_code == 404
    body = response.text
    for leaked in (other.slug, other.name, other.monogram):
        assert leaked not in body


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
    """Same reasoning as the unknown-slug case: a real tenant has to exist
    for the 404 to prove the reserved label wasn't just an empty lookup."""
    other = await make_workspace(db_session, slug="acme")
    await db_session.commit()

    response = await client.get("/api/public/workspaces/api")

    assert response.status_code == 404
    body = response.text
    for leaked in (other.slug, other.name, other.monogram):
        assert leaked not in body


async def test_the_unknown_and_reserved_404_bodies_are_byte_identical(
    db_session, client
) -> None:
    """Otherwise a future edit that reworded one message and not the other
    would open a side channel: a caller could distinguish "this slug is
    reserved" from "this slug simply doesn't exist" by the wording alone."""
    await make_workspace(db_session, slug="acme")
    await db_session.commit()

    unknown = await client.get("/api/public/workspaces/nobody")
    reserved = await client.get("/api/public/workspaces/api")

    assert unknown.status_code == reserved.status_code == 404
    assert unknown.content == reserved.content


async def test_a_workspace_cannot_be_slugged_workspaces(
    db_session: AsyncSession,
) -> None:
    """`/workspaces/{slug}` is registered before `/{slug}/kb`, and both are
    two-segment paths under `/public` -- a workspace slugged "workspaces"
    would have `/api/public/workspaces/kb` swallowed by the workspace-lookup
    handler (slug="kb") instead of reaching the KB index for the workspace
    actually named "workspaces"."""
    with pytest.raises(Invalid):
        await workspaces.create_workspace(
            db_session, name="Workspaces Inc", slug="workspaces", monogram="WS"
        )


async def test_a_mixed_case_slug_is_normalised_on_creation(
    db_session: AsyncSession,
) -> None:
    """`resolve_workspace` looks the slug up as `slug.lower()`; storing the
    caller's casing verbatim would make a workspace permanently unreachable
    on its own subdomain."""
    workspace = await workspaces.create_workspace(
        db_session, name="Acme", slug="AcMe", monogram="AC"
    )

    assert workspace.slug == "acme"
