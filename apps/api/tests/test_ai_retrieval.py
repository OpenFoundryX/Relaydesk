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


from relaydesk.services.ai_retrieval import retrieve
from tests.factories import make_workspace


async def test_retrieve_returns_nothing_for_an_empty_knowledge_base(db_session) -> None:
    """No sources means the caller must not call the model at all."""
    workspace = await make_workspace(db_session)
    assert await retrieve(db_session, workspace.id, "how do refunds work") == []
