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


async def test_a_category_can_be_created_under_a_parent(
    db_session: AsyncSession,
) -> None:
    workspace = await make_workspace(db_session)
    parent = await kb_categories.create(
        db_session, workspace.id, "For spenders", KbScope.external
    )

    child = await kb_categories.create(
        db_session,
        workspace.id,
        "Getting started",
        KbScope.external,
        parent_id=parent.id,
    )

    assert child.parent_id == parent.id
    assert child.depth == 1
    assert parent.depth == 0


async def test_three_levels_are_allowed_and_a_fourth_is_not(
    db_session: AsyncSession,
) -> None:
    """The help site renders collection -> section -> sub-section. A fourth
    container level has nowhere to appear, so it is refused at the service
    rather than stored and silently dropped by the renderer."""
    workspace = await make_workspace(db_session)

    collection = await kb_categories.create(
        db_session, workspace.id, "For spenders", KbScope.external
    )
    section = await kb_categories.create(
        db_session, workspace.id, "Expenses", KbScope.external, parent_id=collection.id
    )
    subsection = await kb_categories.create(
        db_session, workspace.id, "Creating expenses", KbScope.external,
        parent_id=section.id,
    )

    assert subsection.depth == 2

    with pytest.raises(Invalid):
        await kb_categories.create(
            db_session, workspace.id, "Too deep", KbScope.external,
            parent_id=subsection.id,
        )


async def test_an_external_category_cannot_be_nested_under_an_internal_one(
    db_session: AsyncSession,
) -> None:
    """The one that matters. Internal and external are separate namespaces,
    and a section that crosses between them would put staff-only articles
    under a collection the public help site walks."""
    workspace = await make_workspace(db_session)
    internal = await kb_categories.create(
        db_session, workspace.id, "Runbooks", KbScope.internal
    )

    with pytest.raises(Invalid):
        await kb_categories.create(
            db_session, workspace.id, "Refunds", KbScope.external,
            parent_id=internal.id,
        )


async def test_a_parent_in_another_workspace_does_not_exist(
    db_session: AsyncSession,
) -> None:
    workspace = await make_workspace(db_session)
    other = await make_workspace(db_session, slug="acme")
    theirs = await kb_categories.create(
        db_session, other.id, "For spenders", KbScope.external
    )

    with pytest.raises(NotFound):
        await kb_categories.create(
            db_session, workspace.id, "Expenses", KbScope.external,
            parent_id=theirs.id,
        )


async def test_cousins_may_share_a_slug_but_siblings_may_not(
    db_session: AsyncSession,
) -> None:
    """Slugs are unique among siblings, not across the workspace. Every
    collection wants a "Getting started"; forcing the second one to be
    "getting-started-2" would put that in the URL forever."""
    workspace = await make_workspace(db_session)
    spenders = await kb_categories.create(
        db_session, workspace.id, "For spenders", KbScope.external
    )
    admins = await kb_categories.create(
        db_session, workspace.id, "For admins", KbScope.external
    )

    under_spenders = await kb_categories.create(
        db_session, workspace.id, "Getting started", KbScope.external,
        parent_id=spenders.id,
    )
    under_admins = await kb_categories.create(
        db_session, workspace.id, "Getting started", KbScope.external,
        parent_id=admins.id,
    )

    assert under_spenders.slug == under_admins.slug == "getting-started"

    with pytest.raises(Conflict):
        await kb_categories.create(
            db_session, workspace.id, "Getting started", KbScope.external,
            parent_id=spenders.id,
        )


async def test_two_root_collections_still_may_not_share_a_slug(
    db_session: AsyncSession,
) -> None:
    """Roots are siblings of each other. Postgres counts NULLs as distinct
    by default, which would quietly let two root collections share a slug
    and make `/help/{slug}` ambiguous."""
    workspace = await make_workspace(db_session)
    await kb_categories.create(db_session, workspace.id, "Billing", KbScope.external)

    with pytest.raises(Conflict):
        await kb_categories.create(
            db_session, workspace.id, "Billing", KbScope.external
        )


async def test_deleting_a_category_that_holds_sub_collections_is_a_conflict(
    db_session: AsyncSession,
) -> None:
    """The same refusal articles already get. Without it the FK raises and
    the caller sees a 500 instead of being told what is in the way."""
    workspace = await make_workspace(db_session)
    collection = await kb_categories.create(
        db_session, workspace.id, "For spenders", KbScope.external
    )
    await kb_categories.create(
        db_session, workspace.id, "Expenses", KbScope.external, parent_id=collection.id
    )

    with pytest.raises(Conflict):
        await kb_categories.delete(db_session, workspace.id, collection.id)


async def test_a_category_carries_a_description_and_an_icon(
    db_session: AsyncSession,
) -> None:
    workspace = await make_workspace(db_session)

    category = await kb_categories.create(
        db_session,
        workspace.id,
        "For spenders",
        KbScope.external,
        description="Track expenses and file reports in a single click.",
        icon="credit-card",
    )

    assert category.description == "Track expenses and file reports in a single click."
    assert category.icon == "credit-card"


async def test_a_category_created_without_them_gets_neither(
    db_session: AsyncSession,
) -> None:
    """Empty, not NULL. The help site renders a card either way and has no
    second branch for a missing blurb."""
    workspace = await make_workspace(db_session)

    category = await kb_categories.create(
        db_session, workspace.id, "Billing", KbScope.external
    )

    assert (category.description, category.icon) == ("", "")


async def test_an_icon_outside_the_set_is_rejected(db_session: AsyncSession) -> None:
    """The icon names a component the console and the help site both look
    up. An arbitrary string renders as a hole in the page, and the failure
    would only ever be seen by a customer."""
    workspace = await make_workspace(db_session)

    with pytest.raises(Invalid):
        await kb_categories.create(
            db_session, workspace.id, "Billing", KbScope.external, icon="skull"
        )


async def test_the_route_creates_a_sub_collection_with_a_face(
    db_session, client
) -> None:
    """Everything the help site draws on a card -- where it sits, its blurb,
    its icon -- has to be settable by the person writing the articles, not
    only by whoever can run Python against the database."""
    workspace = await make_workspace(db_session)
    admin = await make_member(db_session, workspace, email="nilesh@example.com")
    parent = await kb_categories.create(
        db_session, workspace.id, "For spenders", KbScope.external
    )
    await db_session.commit()
    headers = await sign_in(client, db_session, admin.email)

    response = await client.post(
        "/api/kb/categories",
        json={
            "name": "Expenses",
            "scope": "external",
            "parentId": str(parent.id),
            "description": "Filing and coding what you spent.",
            "icon": "credit-card",
        },
        headers=headers,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["parentId"] == str(parent.id)
    assert body["depth"] == 1
    assert body["description"] == "Filing and coding what you spent."
    assert body["icon"] == "credit-card"


async def test_the_route_edits_a_description_and_an_icon(db_session, client) -> None:
    workspace = await make_workspace(db_session)
    admin = await make_member(db_session, workspace, email="nilesh@example.com")
    category = await kb_categories.create(
        db_session, workspace.id, "Billing", KbScope.external
    )
    await db_session.commit()
    headers = await sign_in(client, db_session, admin.email)

    response = await client.patch(
        f"/api/kb/categories/{category.id}",
        json={"description": "Invoices and refunds.", "icon": "shield"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["description"] == "Invoices and refunds."
    assert response.json()["icon"] == "shield"


async def test_the_route_refuses_an_icon_outside_the_set(db_session, client) -> None:
    """The name is looked up in a fixed table by both the console and the
    help site. Anything else renders as a hole in a customer's page."""
    workspace = await make_workspace(db_session)
    admin = await make_member(db_session, workspace, email="nilesh@example.com")
    category = await kb_categories.create(
        db_session, workspace.id, "Billing", KbScope.external
    )
    await db_session.commit()
    headers = await sign_in(client, db_session, admin.email)

    response = await client.patch(
        f"/api/kb/categories/{category.id}",
        json={"icon": "skull"},
        headers=headers,
    )

    # 422 is what `Invalid` maps to. Asserting the message too, so this
    # cannot pass on some unrelated schema rejection that happens to share
    # the status.
    assert response.status_code == 422
    assert "icons" in response.json()["error"]["message"]
