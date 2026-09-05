import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import NotFound
from relaydesk.models.kb import ArticleStatus, KbScope
from relaydesk.services import kb_articles, kb_categories
from tests.factories import make_member, make_workspace, sign_in

EMPTY_DOC = {"type": "doc", "content": []}


def _doc(text: str) -> dict:
    return {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


async def _setup(session, *, slug="chronon", scope=KbScope.external):
    workspace = await make_workspace(session, slug=slug)
    # ``.test`` is an IANA reserved TLD that pydantic's EmailStr rejects
    # outright, and the route test below logs in for real -- so ".dev"
    # stands in, matching the default fixture email's domain.
    author = await make_member(session, workspace, email=f"a@{slug}.dev")
    category = await kb_categories.create(session, workspace.id, "Billing", scope)
    return workspace, author, category


async def test_a_new_article_starts_as_a_draft(db_session: AsyncSession) -> None:
    """The console navigates straight to the editor after creating, so the row
    must exist before anyone types -- image upload needs something to attach to."""
    workspace, author, category = await _setup(db_session)

    article = await kb_articles.create(
        db_session, workspace.id, category.id, "Handling a refund", author
    )

    assert article.status is ArticleStatus.draft
    assert article.slug == "handling-a-refund"
    assert article.published_at is None
    assert article.author_user_id == author.id
    assert article.doc == EMPTY_DOC


async def test_a_slug_collision_within_a_category_is_suffixed(
    db_session: AsyncSession,
) -> None:
    """Two articles may legitimately share a title; the URL cannot collide."""
    workspace, author, category = await _setup(db_session)

    first = await kb_articles.create(
        db_session, workspace.id, category.id, "Refunds", author
    )
    second = await kb_articles.create(
        db_session, workspace.id, category.id, "Refunds", author
    )

    assert first.slug == "refunds"
    assert second.slug == "refunds-2"


async def test_the_same_slug_is_fine_in_another_category(
    db_session: AsyncSession,
) -> None:
    workspace, author, category = await _setup(db_session)
    other = await kb_categories.create(
        db_session, workspace.id, "Returns", KbScope.external
    )

    a = await kb_articles.create(
        db_session, workspace.id, category.id, "Overview", author
    )
    b = await kb_articles.create(db_session, workspace.id, other.id, "Overview", author)

    assert a.slug == b.slug == "overview"


async def test_updating_the_body_extracts_text_for_search(
    db_session: AsyncSession,
) -> None:
    workspace, author, category = await _setup(db_session)
    article = await kb_articles.create(
        db_session, workspace.id, category.id, "Refunds", author
    )

    await kb_articles.update(
        db_session, workspace.id, article.id, doc=_doc("Issued within thirty days.")
    )

    assert article.body_text == "Issued within thirty days."


async def test_an_empty_excerpt_is_derived_from_the_body(
    db_session: AsyncSession,
) -> None:
    """The excerpt is what both the console list and the public index render
    under every title, so it is never left blank."""
    workspace, author, category = await _setup(db_session)
    article = await kb_articles.create(
        db_session, workspace.id, category.id, "Refunds", author
    )

    await kb_articles.update(
        db_session, workspace.id, article.id, doc=_doc("Issued within thirty days.")
    )

    assert article.excerpt == "Issued within thirty days."


async def test_an_authored_excerpt_is_not_overwritten(db_session: AsyncSession) -> None:
    workspace, author, category = await _setup(db_session)
    article = await kb_articles.create(
        db_session, workspace.id, category.id, "Refunds", author
    )

    await kb_articles.update(
        db_session, workspace.id, article.id, excerpt="Read this first."
    )
    await kb_articles.update(
        db_session, workspace.id, article.id, doc=_doc("Body text here.")
    )

    assert article.excerpt == "Read this first."


async def test_renaming_an_article_does_not_change_its_slug(
    db_session: AsyncSession,
) -> None:
    """The slug is the published URL. Renaming must not break a bookmark."""
    workspace, author, category = await _setup(db_session)
    article = await kb_articles.create(
        db_session, workspace.id, category.id, "Refunds", author
    )

    await kb_articles.update(
        db_session, workspace.id, article.id, title="Refunds and credits"
    )

    assert article.title == "Refunds and credits"
    assert article.slug == "refunds"


async def test_moving_an_article_to_a_category_in_the_other_scope_is_refused(
    db_session: AsyncSession,
) -> None:
    """Scope lives on the category, so moving across scopes would silently
    change who can read the article."""
    from relaydesk.errors import Invalid

    workspace, author, category = await _setup(db_session)
    internal = await kb_categories.create(
        db_session, workspace.id, "Runbooks", KbScope.internal
    )
    article = await kb_articles.create(
        db_session, workspace.id, category.id, "Refunds", author
    )

    with pytest.raises(Invalid):
        await kb_articles.update(
            db_session, workspace.id, article.id, category_id=internal.id
        )


async def test_another_workspaces_article_is_a_404(db_session: AsyncSession) -> None:
    mine, author, category = await _setup(db_session, slug="mine")
    theirs, _, _ = await _setup(db_session, slug="theirs")
    article = await kb_articles.create(
        db_session, mine.id, category.id, "Refunds", author
    )

    with pytest.raises(NotFound):
        await kb_articles.get(db_session, theirs.id, article.id)


async def test_a_category_from_another_workspace_cannot_be_used(
    db_session: AsyncSession,
) -> None:
    mine, author, _ = await _setup(db_session, slug="mine")
    _, _, theirs_category = await _setup(db_session, slug="theirs")

    with pytest.raises(NotFound):
        await kb_articles.create(
            db_session, mine.id, theirs_category.id, "Refunds", author
        )


async def test_listing_filters_by_scope(db_session: AsyncSession) -> None:
    workspace, author, external = await _setup(db_session)
    internal = await kb_categories.create(
        db_session, workspace.id, "Runbooks", KbScope.internal
    )
    await kb_articles.create(
        db_session, workspace.id, external.id, "Public one", author
    )
    await kb_articles.create(
        db_session, workspace.id, internal.id, "Private one", author
    )

    rows = await kb_articles.list_for(db_session, workspace.id, scope=KbScope.internal)

    assert [a.title for a in rows] == ["Private one"]


async def test_the_route_creates_and_reads_an_article(db_session, client) -> None:
    workspace, author, category = await _setup(db_session)
    await db_session.commit()
    headers = await sign_in(client, db_session, author.email)

    created = await client.post(
        "/api/kb/articles",
        json={"categoryId": str(category.id), "title": "Refunds"},
        headers=headers,
    )
    assert created.status_code == 201
    article_id = created.json()["id"]

    fetched = await client.get(f"/api/kb/articles/{article_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["slug"] == "refunds"
    assert fetched.json()["status"] == "draft"
