import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Conflict, Invalid, NotFound
from relaydesk.models.kb import ArticleStatus, KbArticle, KbScope
from relaydesk.services import kb_categories
from relaydesk.services.kb_text import slugify
from tests.factories import make_member, make_workspace, sign_in


async def _article(session, workspace, category, *, title="Refunds"):
    article = KbArticle(
        workspace_id=workspace.id,
        category_id=category.id,
        title=title,
        slug=slugify(title),
        excerpt="",
        doc={"type": "doc", "content": []},
        body_text="",
        status=ArticleStatus.draft,
    )
    session.add(article)
    await session.flush()
    return article


async def test_a_category_gets_a_slug_from_its_name(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)

    category = await kb_categories.create(
        db_session, workspace.id, "Billing & Refunds", KbScope.external
    )

    assert category.slug == "billing-refunds"
    assert category.scope is KbScope.external


async def test_the_same_name_in_both_scopes_is_allowed(
    db_session: AsyncSession,
) -> None:
    """Internal and external are separate namespaces."""
    workspace = await make_workspace(db_session)

    await kb_categories.create(db_session, workspace.id, "Billing", KbScope.internal)
    await kb_categories.create(db_session, workspace.id, "Billing", KbScope.external)


async def test_a_duplicate_name_in_one_scope_is_a_conflict(
    db_session: AsyncSession,
) -> None:
    workspace = await make_workspace(db_session)
    await kb_categories.create(db_session, workspace.id, "Billing", KbScope.external)

    with pytest.raises(Conflict):
        await kb_categories.create(
            db_session, workspace.id, "Billing", KbScope.external
        )


@pytest.mark.parametrize("name", ["Images", "images", "Search", "search"])
async def test_a_reserved_slug_cannot_be_used_for_a_category(
    db_session: AsyncSession, name: str
) -> None:
    """`images` and `search` are reserved by the public KB routes --
    `/kb/images/{id}` and `/kb/search` sit at the same path depth as
    `/kb/{category_slug}/{article_slug}` -- so a category slugifying to
    either would have every one of its articles swallowed by the wrong
    handler."""
    workspace = await make_workspace(db_session)

    with pytest.raises(Invalid):
        await kb_categories.create(db_session, workspace.id, name, KbScope.external)


async def test_an_ordinary_category_slug_is_unaffected(
    db_session: AsyncSession,
) -> None:
    workspace = await make_workspace(db_session)

    category = await kb_categories.create(
        db_session, workspace.id, "Billing", KbScope.external
    )

    assert category.slug == "billing"


async def test_new_categories_append_to_the_end(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)

    first = await kb_categories.create(
        db_session, workspace.id, "One", KbScope.external
    )
    second = await kb_categories.create(
        db_session, workspace.id, "Two", KbScope.external
    )

    assert (first.position, second.position) == (0, 1)


async def test_listing_returns_categories_in_position_order_with_counts(
    db_session: AsyncSession,
) -> None:
    workspace = await make_workspace(db_session)
    billing = await kb_categories.create(
        db_session, workspace.id, "Billing", KbScope.external
    )
    await kb_categories.create(db_session, workspace.id, "Returns", KbScope.external)
    await _article(db_session, workspace, billing, title="Refunds")
    await _article(db_session, workspace, billing, title="Chargebacks")

    rows = await kb_categories.list_for(db_session, workspace.id, KbScope.external)

    assert [(c.name, n) for c, n in rows] == [("Billing", 2), ("Returns", 0)]


async def test_listing_is_scoped_to_one_scope(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)
    await kb_categories.create(
        db_session, workspace.id, "Internal only", KbScope.internal
    )

    rows = await kb_categories.list_for(db_session, workspace.id, KbScope.external)

    assert rows == []


async def test_deleting_a_category_that_holds_articles_is_a_conflict(
    db_session: AsyncSession,
) -> None:
    """Cascading here would delete a workspace's documentation silently."""
    workspace = await make_workspace(db_session)
    category = await kb_categories.create(
        db_session, workspace.id, "Billing", KbScope.external
    )
    await _article(db_session, workspace, category)

    with pytest.raises(Conflict):
        await kb_categories.delete(db_session, workspace.id, category.id)


async def test_an_empty_category_can_be_deleted(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)
    category = await kb_categories.create(
        db_session, workspace.id, "Billing", KbScope.external
    )

    await kb_categories.delete(db_session, workspace.id, category.id)

    assert (
        await kb_categories.list_for(db_session, workspace.id, KbScope.external) == []
    )


async def test_another_workspaces_category_is_a_404(db_session: AsyncSession) -> None:
    mine = await make_workspace(db_session, slug="mine")
    theirs = await make_workspace(db_session, slug="theirs")
    category = await kb_categories.create(
        db_session, mine.id, "Billing", KbScope.external
    )

    with pytest.raises(NotFound):
        await kb_categories.delete(db_session, theirs.id, category.id)


async def test_the_route_lists_categories(db_session, client) -> None:
    workspace = await make_workspace(db_session)
    member = await make_member(db_session, workspace, email="nilesh@example.com")
    await kb_categories.create(db_session, workspace.id, "Billing", KbScope.external)
    await db_session.commit()
    headers = await sign_in(client, db_session, member.email)

    response = await client.get("/api/kb/categories?scope=external", headers=headers)

    assert response.status_code == 200
    assert response.json()[0]["slug"] == "billing"
    assert response.json()[0]["articleCount"] == 0


async def test_creating_a_category_requires_admin(db_session, client) -> None:
    from relaydesk.models.membership import Role

    workspace = await make_workspace(db_session)
    agent = await make_member(
        db_session, workspace, email="sara@example.com", role=Role.agent
    )
    await db_session.commit()
    headers = await sign_in(client, db_session, agent.email)

    response = await client.post(
        "/api/kb/categories",
        json={"name": "Billing", "scope": "external"},
        headers=headers,
    )

    assert response.status_code == 403


async def test_updating_a_category_requires_admin(db_session, client) -> None:
    from relaydesk.models.membership import Role

    workspace = await make_workspace(db_session)
    category = await kb_categories.create(
        db_session, workspace.id, "Billing", KbScope.external
    )
    agent = await make_member(
        db_session, workspace, email="sara@example.com", role=Role.agent
    )
    await db_session.commit()
    headers = await sign_in(client, db_session, agent.email)

    response = await client.patch(
        f"/api/kb/categories/{category.id}",
        json={"name": "Refunds"},
        headers=headers,
    )

    assert response.status_code == 403


async def test_deleting_a_category_requires_admin(db_session, client) -> None:
    from relaydesk.models.membership import Role

    workspace = await make_workspace(db_session)
    category = await kb_categories.create(
        db_session, workspace.id, "Billing", KbScope.external
    )
    agent = await make_member(
        db_session, workspace, email="sara@example.com", role=Role.agent
    )
    await db_session.commit()
    headers = await sign_in(client, db_session, agent.email)

    response = await client.delete(f"/api/kb/categories/{category.id}", headers=headers)

    assert response.status_code == 403
