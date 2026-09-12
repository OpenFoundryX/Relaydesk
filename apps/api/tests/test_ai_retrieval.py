import uuid

from relaydesk.services.ai_retrieval import Source, render_context, resolve_citations


def _source(number: int, title: str = "Refunds") -> Source:
    return Source(
        number=number,
        article_id=uuid.uuid4(),
        title=title,
        path="billing/refunds",
        body="We refund any plan in full within 14 days.",
    )


def test_render_numbers_the_sources_for_the_model():
    rendered = render_context([_source(1), _source(2, "Cancelling")])
    assert "[1] Refunds" in rendered
    assert "[2] Cancelling" in rendered


def test_resolves_a_cited_marker_to_its_source():
    sources = [_source(1), _source(2, "Cancelling")]
    cited = resolve_citations("You can ask for one [1].", sources)
    assert [source.number for source in cited] == [1]


def test_an_invented_marker_resolves_to_nothing():
    """The whole point of resolving server-side: a fabricated citation cannot render."""
    sources = [_source(1)]
    assert resolve_citations("See [7] and [9].", sources) == []


def test_each_source_is_returned_once_however_often_it_is_cited():
    sources = [_source(1)]
    cited = resolve_citations("[1] and again [1] and once more [1]", sources)
    assert len(cited) == 1


def test_citations_come_back_in_the_order_they_were_cited():
    sources = [_source(1), _source(2, "Cancelling"), _source(3, "Billing")]
    cited = resolve_citations("First [3], then [1].", sources)
    assert [source.number for source in cited] == [3, 1]


from relaydesk.models.kb import ArticleStatus, KbArticle, KbCategory, KbScope
from relaydesk.services.ai_retrieval import retrieve
from tests.factories import make_workspace

REFUND_BODY = (
    "We offer refunds within thirty days of your original payment. To "
    "request a refund, contact support with your order number and we will "
    "credit the original payment method. Refunds for annual subscriptions "
    "are prorated based on the unused portion of the term. Refunds appear "
    "on your statement within five to ten business days, depending on your "
    "bank. Digital products purchased by mistake are refundable within "
    "forty eight hours of purchase. Shipping charges on physical returns "
    "are not refunded unless the item arrived damaged."
)


async def _publish(
    db_session,
    workspace,
    *,
    title: str = "Refunds and returns",
    slug: str = "refunds-and-returns",
    body: str = REFUND_BODY,
    scope: KbScope = KbScope.external,
    status: ArticleStatus = ArticleStatus.published,
) -> KbArticle:
    """A published, externally-scoped article with real body text.

    Setting ``body_text`` directly rather than going through
    ``kb_articles.update`` (which derives it from ``doc``): the generated
    ``search_vector`` column is a pure function of ``body_text``, and that
    is the only thing retrieval's match runs against.
    """
    category = KbCategory(
        workspace_id=workspace.id, name=f"Billing {slug}", slug=f"billing-{slug}",
        scope=scope, position=0,
    )
    db_session.add(category)
    await db_session.flush()
    article = KbArticle(
        workspace_id=workspace.id, category_id=category.id,
        title=title, slug=slug,
        excerpt="How refunds work.",
        doc={"type": "doc", "content": []},
        body_text=body,
        status=status,
    )
    db_session.add(article)
    await db_session.flush()
    return article


async def test_retrieve_returns_nothing_for_an_empty_knowledge_base(db_session) -> None:
    """No sources means the caller must not call the model at all."""
    workspace = await make_workspace(db_session)
    assert await retrieve(db_session, workspace.id, "how do refunds work") == []


async def test_retrieve_matches_a_natural_language_question_on_any_word(
    db_session,
) -> None:
    """The regression case: every word of the question need not appear.

    `websearch_to_tsquery` (what the help site's search box uses) would AND
    every lexeme together and find nothing here, because the article never
    says the word "work". Retrieval must match on the words it shares --
    "refunds" -- not demand all of them.
    """
    workspace = await make_workspace(db_session)
    article = await _publish(db_session, workspace)

    sources = await retrieve(db_session, workspace.id, "How do refunds work?")

    assert [source.article_id for source in sources] == [article.id]
    # The model reads the real article text, not the 400-character blurb.
    assert sources[0].body == REFUND_BODY


async def test_retrieve_returns_nothing_when_no_article_shares_a_word(
    db_session,
) -> None:
    workspace = await make_workspace(db_session)
    await _publish(db_session, workspace)

    sources = await retrieve(
        db_session, workspace.id, "what is the weather forecast in paris today"
    )
    assert sources == []


async def test_retrieve_returns_nothing_for_a_stop_word_only_question(
    db_session,
) -> None:
    workspace = await make_workspace(db_session)
    await _publish(db_session, workspace)

    assert await retrieve(db_session, workspace.id, "the a an is") == []


async def test_retrieve_returns_nothing_for_an_empty_question(db_session) -> None:
    workspace = await make_workspace(db_session)
    await _publish(db_session, workspace)

    assert await retrieve(db_session, workspace.id, "") == []


async def test_retrieve_never_returns_a_draft_article(db_session) -> None:
    """A draft is not public, however well its words match the question."""
    workspace = await make_workspace(db_session)
    await _publish(db_session, workspace, status=ArticleStatus.draft)

    sources = await retrieve(db_session, workspace.id, "how do refunds work")
    assert sources == []


async def test_retrieve_never_returns_an_internal_scope_article(db_session) -> None:
    """An internal article is for agents, not anonymous widget visitors."""
    workspace = await make_workspace(db_session)
    await _publish(db_session, workspace, scope=KbScope.internal)

    sources = await retrieve(db_session, workspace.id, "how do refunds work")
    assert sources == []


async def test_retrieve_never_crosses_workspaces(db_session) -> None:
    workspace = await make_workspace(db_session)
    other = await make_workspace(db_session, slug="other")
    await _publish(db_session, other)

    sources = await retrieve(db_session, workspace.id, "how do refunds work")
    assert sources == []


async def test_a_long_pasted_question_does_not_blow_the_stack(db_session) -> None:
    """A 2000-character question is inside the schema's own limit.

    The first disjunctive query accumulated one nesting level per word and
    SQLAlchemy compiled that recursively, so a 160-word question raised
    `RecursionError` -- half the length `WidgetAskIn` advertises. The route
    turned it into a silent degrade with no audit row, which is the exact
    symptom the disjunctive query was written to cure.
    """
    workspace = await make_workspace(db_session)
    # DISTINCT words, not a repeated phrase: the query deduplicates, so a
    # question repeating nine words builds a nine-node tree however long it
    # is, and would pass this test while the defect was wide open.
    question = " ".join(f"word{index}" for index in range(260))[:2000]

    assert await retrieve(db_session, workspace.id, question) == []


async def test_retrieval_is_bounded_in_sources_and_in_body(db_session) -> None:
    """The per-call cost bound, which nothing else asserts.

    What a question costs is decided here: at most five articles, each
    trimmed to `BODY_LIMIT`. Spec D5 calls cost an abuse surface, and both
    halves of that bound moved into `kb_public` when retrieval became
    disjunctive -- further from the tests that might have noticed. Raising
    the limit to 100, or `BODY_LIMIT` to 200000, previously passed the
    entire suite.
    """
    workspace = await make_workspace(db_session)
    for index in range(8):
        await _publish(
            db_session,
            workspace,
            title=f"Refunds {index}",
            slug=f"refunds-{index}",
            body="We refund any plan in full within 14 days. " * 400,
        )

    sources = await retrieve(db_session, workspace.id, "refund")

    assert len(sources) <= 5, "a question must not pull in unbounded sources"
    # A literal, not `BODY_LIMIT`. Asserting against the constant makes the
    # bound move with the thing under test: raising it to 200000 passed
    # this test unchanged, because both sides moved together.
    assert all(len(source.body) <= 2000 for source in sources), (
        "an article's body must be trimmed before it reaches the model"
    )
