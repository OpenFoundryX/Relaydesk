import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models.kb import ArticleStatus, KbArticle, KbCategory, KbScope
from tests.factories import make_workspace


async def _category(
    session: AsyncSession, workspace, *, scope=KbScope.external, slug="billing"
):
    category = KbCategory(
        workspace_id=workspace.id, scope=scope, name="Billing", slug=slug, position=0
    )
    session.add(category)
    await session.flush()
    return category


def _doc(text: str) -> dict:
    return {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": text}]}
        ],
    }


async def test_an_article_stores_its_document_as_json(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)
    category = await _category(db_session, workspace)

    article = KbArticle(
        workspace_id=workspace.id,
        category_id=category.id,
        title="Refunds",
        slug="refunds",
        excerpt="How refunds work.",
        doc=_doc("Refunds are issued within 30 days."),
        body_text="Refunds are issued within 30 days.",
        status=ArticleStatus.draft,
    )
    db_session.add(article)
    await db_session.flush()

    assert article.doc["content"][0]["content"][0]["text"].startswith("Refunds")
    assert article.status is ArticleStatus.draft
    assert article.published_at is None


async def test_two_articles_cannot_share_a_slug_in_one_category(
    db_session: AsyncSession,
) -> None:
    """The slug is the public URL, so a collision inside a category would make
    one of the two unreachable."""
    workspace = await make_workspace(db_session)
    category = await _category(db_session, workspace)

    for _ in range(2):
        db_session.add(
            KbArticle(
                workspace_id=workspace.id,
                category_id=category.id,
                title="Refunds",
                slug="refunds",
                excerpt="",
                doc=_doc("x"),
                body_text="x",
                status=ArticleStatus.draft,
            )
        )

    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_the_same_slug_is_fine_in_a_different_category(
    db_session: AsyncSession,
) -> None:
    workspace = await make_workspace(db_session)
    billing = await _category(db_session, workspace, slug="billing")
    returns = await _category(db_session, workspace, slug="returns")

    for category in (billing, returns):
        db_session.add(
            KbArticle(
                workspace_id=workspace.id,
                category_id=category.id,
                title="Overview",
                slug="overview",
                excerpt="",
                doc=_doc("x"),
                body_text="x",
                status=ArticleStatus.draft,
            )
        )
    await db_session.flush()


async def test_categories_are_unique_per_scope_not_globally(
    db_session: AsyncSession,
) -> None:
    """Internal and external are separate namespaces -- a workspace may well
    want a 'Billing' category in both."""
    workspace = await make_workspace(db_session)

    await _category(db_session, workspace, scope=KbScope.internal, slug="billing")
    await _category(db_session, workspace, scope=KbScope.external, slug="billing")


async def test_search_vector_is_populated_from_title_and_body(
    db_session: AsyncSession,
) -> None:
    """It is a generated column, so it must be maintained by Postgres rather
    than by anything remembering to update it."""
    workspace = await make_workspace(db_session)
    category = await _category(db_session, workspace)
    article = KbArticle(
        workspace_id=workspace.id,
        category_id=category.id,
        title="Refunds",
        slug="refunds",
        excerpt="",
        doc=_doc("x"),
        body_text="issued within thirty days",
        status=ArticleStatus.draft,
    )
    db_session.add(article)
    await db_session.flush()

    hit = await db_session.scalar(
        sa.select(KbArticle.id).where(
            KbArticle.id == article.id,
            KbArticle.search_vector.op("@@")(
                sa.func.plainto_tsquery("english", "thirty")
            ),
        )
    )
    assert hit == article.id
