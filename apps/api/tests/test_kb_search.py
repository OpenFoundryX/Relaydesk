from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models.kb import ArticleStatus, KbScope
from relaydesk.services import kb_articles, kb_categories
from tests.factories import make_member, make_workspace


def _doc(text: str) -> dict:
    return {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


async def _write(
    session, workspace, category, author, title, body, *, status=ArticleStatus.draft
):
    article = await kb_articles.create(
        session, workspace.id, category.id, title, author
    )
    await kb_articles.update(session, workspace.id, article.id, doc=_doc(body))
    if status is not ArticleStatus.draft:
        article.status = status
        await session.flush()
    return article


async def _setup(session, slug="chronon"):
    workspace = await make_workspace(session, slug=slug)
    author = await make_member(session, workspace, email=f"a@{slug}.test")
    category = await kb_categories.create(
        session, workspace.id, "Billing", KbScope.external
    )
    return workspace, author, category


async def test_search_matches_the_body(db_session: AsyncSession) -> None:
    workspace, author, category = await _setup(db_session)
    await _write(
        db_session, workspace, category, author, "Refunds", "Issued within thirty days."
    )

    hits = await kb_articles.search(db_session, workspace.id, "thirty")

    assert [a.title for a in hits] == ["Refunds"]


async def test_search_matches_the_title(db_session: AsyncSession) -> None:
    workspace, author, category = await _setup(db_session)
    await _write(
        db_session, workspace, category, author, "Chargebacks", "Nothing relevant here."
    )

    hits = await kb_articles.search(db_session, workspace.id, "chargebacks")

    assert [a.title for a in hits] == ["Chargebacks"]


async def test_search_stems_english_words(db_session: AsyncSession) -> None:
    """to_tsvector('english') is what makes 'refund' find 'refunded'."""
    workspace, author, category = await _setup(db_session)
    await _write(
        db_session, workspace, category, author, "Policy", "The charge was refunded."
    )

    assert len(await kb_articles.search(db_session, workspace.id, "refund")) == 1


async def test_search_never_crosses_a_workspace(db_session: AsyncSession) -> None:
    mine, mine_author, mine_category = await _setup(db_session, slug="mine")
    theirs, theirs_author, theirs_category = await _setup(db_session, slug="theirs")
    await _write(
        db_session, theirs, theirs_category, theirs_author, "Secret", "thirty days"
    )

    assert await kb_articles.search(db_session, mine.id, "thirty") == []


async def test_published_only_excludes_drafts(db_session: AsyncSession) -> None:
    """This is the mode the public hub uses; a draft leaking into it would
    publish something nobody approved."""
    workspace, author, category = await _setup(db_session)
    await _write(db_session, workspace, category, author, "Draft one", "thirty days")
    await _write(
        db_session,
        workspace,
        category,
        author,
        "Live one",
        "thirty days",
        status=ArticleStatus.published,
    )

    hits = await kb_articles.search(
        db_session, workspace.id, "thirty", published_only=True
    )

    assert [a.title for a in hits] == ["Live one"]


async def test_search_can_be_scoped(db_session: AsyncSession) -> None:
    workspace, author, external = await _setup(db_session)
    internal = await kb_categories.create(
        db_session, workspace.id, "Runbooks", KbScope.internal
    )
    await _write(db_session, workspace, external, author, "Public", "thirty days")
    await _write(db_session, workspace, internal, author, "Private", "thirty days")

    hits = await kb_articles.search(
        db_session, workspace.id, "thirty", scope=KbScope.internal
    )

    assert [a.title for a in hits] == ["Private"]


async def test_an_empty_query_returns_nothing(db_session: AsyncSession) -> None:
    """Rather than every article, which is what a bare tsquery would do."""
    workspace, author, category = await _setup(db_session)
    await _write(db_session, workspace, category, author, "Refunds", "thirty days")

    assert await kb_articles.search(db_session, workspace.id, "   ") == []


async def test_punctuation_in_a_query_does_not_raise(db_session: AsyncSession) -> None:
    """This is user input from a public search box. `to_tsquery` would raise on
    most of these; websearch_to_tsquery is what makes them safe."""
    workspace, author, category = await _setup(db_session)
    await _write(db_session, workspace, category, author, "Refunds", "thirty days")

    for query in ["&&&", "a | b", '"unclosed', "!!!", "thirty OR days", "-thirty"]:
        await kb_articles.search(db_session, workspace.id, query)
