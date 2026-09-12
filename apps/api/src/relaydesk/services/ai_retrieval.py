"""What the model is allowed to know, and how a citation becomes a link.

Retrieval runs before the model does. If nothing matches the question at
all the model is never called -- an answer with no source material is the
failure this module exists to prevent, not an edge case to handle
afterwards.

The retrieved articles are numbered, and the model is instructed to cite
them as ``[n]``. Those markers are mapped back to articles **here**, on the
server, from the numbering the server itself issued. A model that invents
``[9]`` when it was given five sources produces no citation, because nine
resolves to nothing. That is the difference between citing and appearing to
cite, and it is why the panel's links can be trusted (spec D3).
"""

import re
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models.kb import KbArticle, KbCategory
from relaydesk.services import kb_public

_MARKER = re.compile(r"\[(\d{1,2})\]")


@dataclass(frozen=True)
class Source:
    """One retrieved article, as the model will see it and as it resolves back."""

    number: int
    article_id: uuid.UUID
    title: str
    path: str
    body: str


# Five articles at this length is roughly 2.5k tokens of context, which the
# daily budget carries comfortably. Lower it before lowering the article
# count: fewer sources is a worse answer than shorter ones.
BODY_LIMIT = 2000


def _path(ancestors: list[KbCategory], article: KbArticle) -> str:
    return "/".join([*(category.slug for category in ancestors), article.slug])


def _body(article: KbArticle) -> str:
    """The article's text, not its blurb.

    ``excerpt`` is ``String(400)`` and is written to sit under a search
    result. A model handed five of those cannot answer from them, and a
    model that cannot answer from its sources does not say so -- it fills
    the gap from training data, which is the failure grounding exists to
    prevent.

    ``body_text`` is the column ``search_vector`` is computed from
    (``kb.py``: ``to_tsvector('english', title || ' ' || body_text)``), so
    what the model reads is literally what search matched on. It is
    extracted once on write in ``kb_articles.update``; re-deriving it here
    from ``doc`` would parse the same JSON again on every question to
    arrive at the same string.
    """
    text = article.body_text.strip()
    return text[:BODY_LIMIT] if text else article.excerpt


async def retrieve(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    question: str,
    *,
    limit: int = 5,
) -> list[Source]:
    """The published articles this question may be answered from, numbered.

    Matches on **any** significant word the question contains, ranked best
    first, not on every word matching at once: ``kb_public.search_any`` is
    built for a whole sentence, unlike ``kb_public.search`` (the help
    site's and console's search box), whose all-terms-must-match query
    returns nothing for most ordinary phrasing when handed prose instead
    of keywords. See ``kb_public._disjunctive_tsquery`` for how the match
    itself is built, and ``kb_public._visible`` for the visibility rules
    it shares with everything else the public help site can reach --
    published status, external scope, nothing else.

    Returns an empty list when nothing matched -- including a question
    that is only stop words, or empty -- and the caller must treat that as
    "do not call the model" rather than as "call it with no context": a
    model given no sources will answer from its training data, which is
    exactly what grounding exists to prevent.
    """
    articles = await kb_public.search_any(session, workspace_id, question, limit=limit)
    if not articles:
        return []

    ancestors = await kb_public.paths_for(session, workspace_id, articles)
    return [
        Source(
            number=index,
            article_id=article.id,
            title=article.title,
            path=_path(ancestors.get(article.id, []), article),
            body=_body(article),
        )
        for index, article in enumerate(articles, start=1)
    ]


def render_context(sources: list[Source]) -> str:
    """The sources as the model receives them, numbered for citation."""
    return "\n\n".join(
        f"[{source.number}] {source.title}\n{source.body}" for source in sources
    )


def resolve_citations(answer: str, sources: list[Source]) -> list[Source]:
    """The sources an answer actually cited, in the order it cited them.

    Out-of-range markers are dropped silently rather than reported: the
    visitor gains nothing from being told the model miscounted, and the
    absence of a link is already the honest signal.
    """
    by_number = {source.number: source for source in sources}
    seen: list[Source] = []
    for match in _MARKER.finditer(answer):
        source = by_number.get(int(match.group(1)))
        if source is not None and source not in seen:
            seen.append(source)
    return seen
