import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Invalid
from relaydesk.models.kb import ArticleStatus, KbScope
from relaydesk.services import kb_articles, kb_categories
from tests.factories import make_member, make_workspace, sign_in


async def _article(session, *, status=ArticleStatus.draft):
    workspace = await make_workspace(session)
    author = await make_member(session, workspace, email="a@example.com")
    category = await kb_categories.create(
        session, workspace.id, "Billing", KbScope.external
    )
    article = await kb_articles.create(
        session, workspace.id, category.id, "Refunds", author
    )
    if status is not ArticleStatus.draft:
        article.status = status
        await session.flush()
    return workspace, author, article


async def test_draft_can_become_ready(db_session: AsyncSession) -> None:
    workspace, _, article = await _article(db_session)

    updated = await kb_articles.set_status(
        db_session, workspace.id, article.id, ArticleStatus.ready
    )

    assert updated.status is ArticleStatus.ready
    assert updated.published_at is None


async def test_publishing_stamps_published_at(db_session: AsyncSession) -> None:
    workspace, _, article = await _article(db_session, status=ArticleStatus.ready)

    updated = await kb_articles.set_status(
        db_session, workspace.id, article.id, ArticleStatus.published
    )

    assert updated.status is ArticleStatus.published
    assert updated.published_at is not None


async def test_draft_cannot_skip_straight_to_published(
    db_session: AsyncSession,
) -> None:
    """The review step is the whole point of having three states."""
    workspace, _, article = await _article(db_session)

    with pytest.raises(Invalid):
        await kb_articles.set_status(
            db_session, workspace.id, article.id, ArticleStatus.published
        )


async def test_published_can_be_unpublished_to_draft(db_session: AsyncSession) -> None:
    workspace, _, article = await _article(db_session, status=ArticleStatus.published)

    updated = await kb_articles.set_status(
        db_session, workspace.id, article.id, ArticleStatus.draft
    )

    assert updated.status is ArticleStatus.draft


async def test_unpublishing_keeps_the_original_publication_date(
    db_session: AsyncSession,
) -> None:
    """published_at records when it first went live, not whether it is live
    now -- status already answers that."""
    workspace, _, article = await _article(db_session, status=ArticleStatus.ready)
    published = await kb_articles.set_status(
        db_session, workspace.id, article.id, ArticleStatus.published
    )
    stamped = published.published_at

    unpublished = await kb_articles.set_status(
        db_session, workspace.id, article.id, ArticleStatus.draft
    )

    assert unpublished.published_at == stamped


async def test_ready_can_go_back_to_draft(db_session: AsyncSession) -> None:
    workspace, _, article = await _article(db_session, status=ArticleStatus.ready)

    updated = await kb_articles.set_status(
        db_session, workspace.id, article.id, ArticleStatus.draft
    )

    assert updated.status is ArticleStatus.draft


async def test_published_cannot_go_back_to_ready(db_session: AsyncSession) -> None:
    workspace, _, article = await _article(db_session, status=ArticleStatus.published)

    with pytest.raises(Invalid):
        await kb_articles.set_status(
            db_session, workspace.id, article.id, ArticleStatus.ready
        )


async def test_an_illegal_transition_over_http_is_a_422(db_session, client) -> None:
    workspace, author, article = await _article(db_session)
    await db_session.commit()
    headers = await sign_in(client, db_session, author.email)

    response = await client.post(
        f"/api/kb/articles/{article.id}/status",
        json={"status": "published"},
        headers=headers,
    )

    assert response.status_code == 422
