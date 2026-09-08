from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.config import get_settings
from relaydesk.errors import NotFound
from relaydesk.models.kb import ArticleStatus, KbImage, KbScope
from relaydesk.services import blobs, kb_articles, kb_categories, kb_images, kb_public
from tests.factories import make_member, make_workspace

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


async def _unsafe_image(session, article, content_type: str) -> KbImage:
    """A row whose stored `content_type` is not on the image allowlist.

    Built directly through the model rather than `kb_images.store`, which
    correctly refuses to write one -- this exists to prove the public read
    path also refuses to trust it.
    """
    content = b"<script>alert(1)</script>"
    digest, key = blobs.write(
        kb_images.storage_root(), article.workspace_id, content
    )
    image = KbImage(
        workspace_id=article.workspace_id,
        article_id=article.id,
        filename="payload.html",
        content_type=content_type,
        size_bytes=len(content),
        sha256=digest,
        storage_key=key,
    )
    session.add(image)
    await session.flush()
    return image


@pytest.fixture(autouse=True)
def image_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "attachment_dir", str(tmp_path))
    return tmp_path


def _doc(text: str) -> dict:
    return {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


async def _published(
    session,
    *,
    slug="acme",
    scope=KbScope.external,
    status=ArticleStatus.published,
):
    workspace = await make_workspace(session, slug=slug)
    author = await make_member(session, workspace, email=f"a@{slug}.dev")
    category = await kb_categories.create(session, workspace.id, "Billing", scope)
    article = await kb_articles.create(
        session, workspace.id, category.id, "Refunds", author
    )
    await kb_articles.update(
        session, workspace.id, article.id, doc=_doc("Within thirty days.")
    )
    article.status = status
    await session.flush()
    return workspace, category, article


async def test_the_root_listing_shows_published_external_articles(
    db_session: AsyncSession,
) -> None:
    workspace, _, _ = await _published(db_session)

    rows = await kb_public.roots(db_session, workspace.id)

    assert [(c.name, n) for c, n in rows] == [("Billing", 1)]


async def test_a_draft_never_appears_publicly(db_session: AsyncSession) -> None:
    workspace, _, _ = await _published(db_session, status=ArticleStatus.draft)

    assert await kb_public.roots(db_session, workspace.id) == []


async def test_a_ready_article_is_not_public_either(db_session: AsyncSession) -> None:
    """Ready means reviewed, not live. Publishing is a separate decision."""
    workspace, _, _ = await _published(db_session, status=ArticleStatus.ready)

    assert await kb_public.roots(db_session, workspace.id) == []


async def test_internal_articles_are_never_public(db_session: AsyncSession) -> None:
    """These are the agent's runbooks. Publishing one would expose internal
    procedure to customers."""
    workspace, _, _ = await _published(db_session, scope=KbScope.internal)

    assert await kb_public.roots(db_session, workspace.id) == []


async def test_an_empty_category_is_omitted_from_the_index(
    db_session: AsyncSession,
) -> None:
    workspace, _, _ = await _published(db_session)
    await kb_categories.create(db_session, workspace.id, "Returns", KbScope.external)

    rows = await kb_public.roots(db_session, workspace.id)

    assert [c.name for c, _ in rows] == ["Billing"]


async def test_an_article_is_readable_by_its_slugs(db_session: AsyncSession) -> None:
    workspace, category, article = await _published(db_session)

    found = await kb_public.resolve(
        db_session, workspace.id, [category.slug, article.slug]
    )

    assert found.article.id == article.id


async def test_an_unpublished_article_is_a_404_not_a_403(
    db_session: AsyncSession,
) -> None:
    """403 would confirm that an article exists at a guessable slug."""
    workspace, category, article = await _published(
        db_session, status=ArticleStatus.draft
    )

    with pytest.raises(NotFound):
        await kb_public.resolve(
            db_session, workspace.id, [category.slug, article.slug]
        )


async def test_another_workspaces_article_is_not_readable(
    db_session: AsyncSession,
) -> None:
    theirs, category, article = await _published(db_session, slug="theirs")
    mine = await make_workspace(db_session, slug="mine")

    with pytest.raises(NotFound):
        await kb_public.resolve(db_session, mine.id, [category.slug, article.slug])


async def test_public_search_excludes_unpublished(db_session: AsyncSession) -> None:
    workspace, _, article = await _published(db_session, status=ArticleStatus.draft)

    assert await kb_public.search(db_session, workspace.id, "thirty") == []


async def test_public_search_excludes_internal_scope_even_when_published(
    db_session: AsyncSession,
) -> None:
    """Task 6's tests exercise scope and published_only independently but
    never together -- this is the combination that is the whole public-
    visibility guarantee, so an internal published article and an external
    draft must both be excluded even though each predicate alone would let
    one of them through."""
    workspace, _, _ = await _published(db_session, scope=KbScope.internal)
    external_category = await kb_categories.create(
        db_session, workspace.id, "Shipping", KbScope.external
    )
    author = await make_member(db_session, workspace, email="b@acme.dev")
    draft = await kb_articles.create(
        db_session, workspace.id, external_category.id, "Late deliveries", author
    )
    await kb_articles.update(
        db_session, workspace.id, draft.id, doc=_doc("Within thirty days of dispatch.")
    )

    assert await kb_public.search(db_session, workspace.id, "thirty") == []


async def test_visibility_and_search_share_one_definition_of_public(
    db_session: AsyncSession, monkeypatch
) -> None:
    """`_visible()` (used by `index`, `article`, and `image`) and `search()`
    must read the definition of "public" from the same place. Patching
    `PUBLIC_STATUS` and seeing both an index query and a search query react
    pins that they share one source rather than each hardcoding
    `ArticleStatus.published` on its own."""
    workspace, _, article = await _published(db_session)
    monkeypatch.setattr(kb_public, "PUBLIC_STATUS", ArticleStatus.ready)

    assert await kb_public.roots(db_session, workspace.id) == []
    assert await kb_public.search(db_session, workspace.id, "thirty") == []


async def test_an_image_on_a_published_article_is_readable(
    db_session: AsyncSession,
) -> None:
    workspace, _, article = await _published(db_session)
    image = await kb_images.store(db_session, article, "s.png", "image/png", PNG)

    row, content = await kb_public.image(db_session, workspace.id, image.id)

    assert content == PNG


async def test_an_image_on_a_draft_article_is_a_404(db_session: AsyncSession) -> None:
    """Otherwise an unpublished article's screenshots are readable by anyone
    who guesses an id -- the article is hidden but its pictures are not."""
    workspace, _, article = await _published(db_session, status=ArticleStatus.draft)
    image = await kb_images.store(db_session, article, "s.png", "image/png", PNG)

    with pytest.raises(NotFound):
        await kb_public.image(db_session, workspace.id, image.id)


async def test_an_image_on_an_internal_article_is_a_404(
    db_session: AsyncSession,
) -> None:
    workspace, _, article = await _published(db_session, scope=KbScope.internal)
    image = await kb_images.store(db_session, article, "s.png", "image/png", PNG)

    with pytest.raises(NotFound):
        await kb_public.image(db_session, workspace.id, image.id)


# -- HTTP routes ----------------------------------------------------------
# The service layer above proves the visibility rule holds; these confirm
# each route actually enforces it rather than trusting a shared code path.

HIDDEN = pytest.mark.parametrize(
    "kwargs",
    [
        {"status": ArticleStatus.draft},
        {"status": ArticleStatus.ready},
        {"scope": KbScope.internal},
    ],
    ids=["draft", "ready", "internal-scope"],
)


async def test_the_index_route_lists_root_collections(
    client, db_session: AsyncSession
) -> None:
    """The front page is collection cards, not every article in the
    workspace. Each card carries the blurb, the icon, and how many articles
    are under it."""
    workspace, _, _ = await _published(db_session)

    response = await client.get(f"/api/public/{workspace.slug}/kb")

    assert response.status_code == 200
    body = response.json()
    assert [c["name"] for c in body] == ["Billing"]
    assert body[0]["articleCount"] == 1
    assert (body[0]["description"], body[0]["icon"]) == ("", "")


@HIDDEN
async def test_the_index_route_omits_hidden_articles(
    client, db_session: AsyncSession, kwargs: dict
) -> None:
    workspace, _, _ = await _published(db_session, **kwargs)

    response = await client.get(f"/api/public/{workspace.slug}/kb")

    assert response.status_code == 200
    assert response.json() == []


async def test_the_index_route_shows_nothing_from_another_workspace(
    client, db_session: AsyncSession
) -> None:
    await _published(db_session, slug="theirs")
    mine = await make_workspace(db_session, slug="mine")

    response = await client.get(f"/api/public/{mine.slug}/kb")

    assert response.status_code == 200
    assert response.json() == []


async def test_the_article_route_serves_a_published_article(
    client, db_session: AsyncSession
) -> None:
    workspace, category, article = await _published(db_session)

    response = await client.get(
        f"/api/public/{workspace.slug}/kb/{category.slug}/{article.slug}"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "article"
    assert body["article"]["title"] == "Refunds"


async def test_the_article_route_reports_when_it_was_last_updated(
    client, db_session: AsyncSession
) -> None:
    """The help site prints this under the body as "Last updated".

    Asserted against the stored row, not merely "the key is present", so
    both dropping the field and filling it from the wrong column fail --
    `published_at` in particular is None here, because `_published` sets
    the status on the model directly.
    """
    workspace, category, article = await _published(db_session)

    response = await client.get(
        f"/api/public/{workspace.slug}/kb/{category.slug}/{article.slug}"
    )

    assert response.status_code == 200
    assert (
        datetime.fromisoformat(response.json()["article"]["updatedAt"])
        == article.updated_at
    )


@HIDDEN
async def test_the_article_route_404s_when_hidden(
    client, db_session: AsyncSession, kwargs: dict
) -> None:
    workspace, category, article = await _published(db_session, **kwargs)

    response = await client.get(
        f"/api/public/{workspace.slug}/kb/{category.slug}/{article.slug}"
    )

    assert response.status_code == 404


async def test_the_article_route_404s_for_a_different_workspace(
    client, db_session: AsyncSession
) -> None:
    _, category, article = await _published(db_session, slug="theirs")
    mine = await make_workspace(db_session, slug="mine")

    response = await client.get(
        f"/api/public/{mine.slug}/kb/{category.slug}/{article.slug}"
    )

    assert response.status_code == 404


async def test_the_search_route_finds_published_external_articles(
    client, db_session: AsyncSession
) -> None:
    workspace, _, _ = await _published(db_session)

    response = await client.get(
        f"/api/public/{workspace.slug}/kb/search", params={"q": "thirty"}
    )

    assert response.status_code == 200
    assert [a["title"] for a in response.json()] == ["Refunds"]


@HIDDEN
async def test_the_search_route_excludes_hidden_articles(
    client, db_session: AsyncSession, kwargs: dict
) -> None:
    workspace, _, _ = await _published(db_session, **kwargs)

    response = await client.get(
        f"/api/public/{workspace.slug}/kb/search", params={"q": "thirty"}
    )

    assert response.status_code == 200
    assert response.json() == []


async def test_the_search_route_finds_nothing_from_another_workspace(
    client, db_session: AsyncSession
) -> None:
    await _published(db_session, slug="theirs")
    mine = await make_workspace(db_session, slug="mine")

    response = await client.get(
        f"/api/public/{mine.slug}/kb/search", params={"q": "thirty"}
    )

    assert response.status_code == 200
    assert response.json() == []


async def test_the_image_route_serves_the_bytes_with_nosniff(
    client, db_session: AsyncSession
) -> None:
    workspace, _, article = await _published(db_session)
    image = await kb_images.store(db_session, article, "s.png", "image/png", PNG)

    response = await client.get(f"/api/public/{workspace.slug}/kb/images/{image.id}")

    assert response.status_code == 200
    assert response.content == PNG
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"


@HIDDEN
async def test_the_image_route_404s_when_the_article_is_hidden(
    client, db_session: AsyncSession, kwargs: dict
) -> None:
    workspace, _, article = await _published(db_session, **kwargs)
    image = await kb_images.store(db_session, article, "s.png", "image/png", PNG)

    response = await client.get(f"/api/public/{workspace.slug}/kb/images/{image.id}")

    assert response.status_code == 404


async def test_the_image_route_404s_for_a_different_workspace(
    client, db_session: AsyncSession
) -> None:
    _, _, article = await _published(db_session, slug="theirs")
    mine = await make_workspace(db_session, slug="mine")
    image = await kb_images.store(db_session, article, "s.png", "image/png", PNG)

    response = await client.get(f"/api/public/{mine.slug}/kb/images/{image.id}")

    assert response.status_code == 404


async def test_the_image_route_refuses_a_content_type_off_the_allowlist(
    client, db_session: AsyncSession
) -> None:
    """`kb_images.store` refuses this on write, but the public read route
    must not trust the stored value regardless -- this is the anonymous,
    unauthenticated origin, so it is the one route where this matters most."""
    workspace, _, article = await _published(db_session)
    image = await _unsafe_image(db_session, article, "text/html")

    response = await client.get(f"/api/public/{workspace.slug}/kb/images/{image.id}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-disposition"] == "attachment"
    assert response.headers["x-content-type-options"] == "nosniff"


async def _publish_in(session, workspace, category, author, title):
    article = await kb_articles.create(
        session, workspace.id, category.id, title, author
    )
    await kb_articles.update(
        session, workspace.id, article.id, doc=_doc("Body.")
    )
    article.status = ArticleStatus.published
    await session.flush()
    return article


async def test_the_root_listing_counts_articles_from_the_whole_subtree(
    db_session: AsyncSession,
) -> None:
    """A collection's card says how many articles are under it, and most of
    them live in its sections rather than directly in it."""
    workspace = await make_workspace(db_session, slug="acme")
    author = await make_member(db_session, workspace, email="a@acme.dev")
    collection = await kb_categories.create(
        db_session, workspace.id, "For spenders", KbScope.external
    )
    section = await kb_categories.create(
        db_session, workspace.id, "Expenses", KbScope.external, parent_id=collection.id
    )
    subsection = await kb_categories.create(
        db_session, workspace.id, "Creating", KbScope.external, parent_id=section.id
    )
    await _publish_in(db_session, workspace, collection, author, "Overview")
    await _publish_in(db_session, workspace, section, author, "My expenses")
    await _publish_in(db_session, workspace, subsection, author, "Add a receipt")

    rows = await kb_public.roots(db_session, workspace.id)

    assert [(c.name, n) for c, n in rows] == [("For spenders", 3)]


async def test_a_collection_with_nothing_published_under_it_is_omitted(
    db_session: AsyncSession,
) -> None:
    """The index has always omitted empty categories. With a tree, "empty"
    has to mean the whole subtree -- otherwise a collection whose only
    articles are drafts two levels down still gets a card, and every link
    behind it 404s."""
    workspace = await make_workspace(db_session, slug="acme")
    author = await make_member(db_session, workspace, email="a@acme.dev")
    collection = await kb_categories.create(
        db_session, workspace.id, "For spenders", KbScope.external
    )
    section = await kb_categories.create(
        db_session, workspace.id, "Expenses", KbScope.external, parent_id=collection.id
    )
    draft = await kb_articles.create(
        db_session, workspace.id, section.id, "Not yet", author
    )
    assert draft.status is ArticleStatus.draft

    assert await kb_public.roots(db_session, workspace.id) == []


async def _spenders_tree(session):
    """collection -> section, with an article directly in each."""
    workspace = await make_workspace(session, slug="acme")
    author = await make_member(session, workspace, email="a@acme.dev")
    collection = await kb_categories.create(
        session, workspace.id, "For spenders", KbScope.external
    )
    section = await kb_categories.create(
        session, workspace.id, "Expenses", KbScope.external, parent_id=collection.id
    )
    overview = await _publish_in(session, workspace, collection, author, "Overview")
    receipts = await _publish_in(session, workspace, section, author, "Add a receipt")
    return workspace, collection, section, overview, receipts


async def test_a_deep_path_resolves_to_the_article_it_names(
    db_session: AsyncSession,
) -> None:
    workspace, collection, section, _, receipts = await _spenders_tree(db_session)

    found = await kb_public.resolve(
        db_session, workspace.id, ["for-spenders", "expenses", "add-a-receipt"]
    )

    assert found.article.id == receipts.id
    assert [c.slug for c in found.ancestors] == ["for-spenders", "expenses"]


async def test_a_category_path_resolves_to_its_children(
    db_session: AsyncSession,
) -> None:
    """What a collection page renders: its sections, and the articles that
    sit directly in it rather than in one of them."""
    workspace, collection, section, overview, _ = await _spenders_tree(db_session)

    found = await kb_public.resolve(db_session, workspace.id, ["for-spenders"])

    assert found.category.id == collection.id
    assert found.ancestors == []
    assert [(s.category.name, s.article_count) for s in found.sections] == [
        ("Expenses", 1)
    ]
    assert [a.title for a in found.articles] == ["Overview"]


async def test_an_unknown_path_is_a_404(db_session: AsyncSession) -> None:
    workspace, _, _, _, _ = await _spenders_tree(db_session)

    with pytest.raises(NotFound):
        await kb_public.resolve(db_session, workspace.id, ["for-spenders", "nope"])


async def test_an_article_is_still_found_at_the_path_it_used_to_have(
    db_session: AsyncSession,
) -> None:
    """Every article the flat KB published lives at /help/{category}/{slug}.
    Moving it into a section must not turn every link to it into a 404, so
    a path that fails the walk falls back to the article's slug -- and comes
    back carrying where it actually lives now, which is what lets the
    caller redirect to the canonical path rather than serve a duplicate."""
    workspace, collection, section, _, receipts = await _spenders_tree(db_session)

    found = await kb_public.resolve(
        db_session, workspace.id, ["for-spenders", "add-a-receipt"]
    )

    assert found.article.id == receipts.id
    assert [c.slug for c in found.ancestors] == ["for-spenders", "expenses"]


async def test_the_fallback_does_not_reach_across_workspaces(
    db_session: AsyncSession,
) -> None:
    workspace, _, _, _, _ = await _spenders_tree(db_session)
    other = await make_workspace(db_session, slug="other")
    author = await make_member(db_session, other, email="a@other.dev")
    theirs = await kb_categories.create(
        db_session, other.id, "Theirs", KbScope.external
    )
    await _publish_in(db_session, other, theirs, author, "Secret sauce")

    with pytest.raises(NotFound):
        await kb_public.resolve(
            db_session, workspace.id, ["for-spenders", "secret-sauce"]
        )


async def test_the_kb_route_serves_a_deep_article_path(
    client, db_session: AsyncSession
) -> None:
    workspace, _, _, _, _ = await _spenders_tree(db_session)

    response = await client.get(
        f"/api/public/{workspace.slug}/kb/for-spenders/expenses/add-a-receipt"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "article"
    assert body["article"]["title"] == "Add a receipt"
    assert [c["slug"] for c in body["ancestors"]] == ["for-spenders", "expenses"]


async def test_the_kb_route_serves_a_collection_page(
    client, db_session: AsyncSession
) -> None:
    """One request per page: the collection itself, its breadcrumb, the
    sections under it with their counts, and the articles sitting directly
    in it."""
    workspace, _, _, _, _ = await _spenders_tree(db_session)

    response = await client.get(f"/api/public/{workspace.slug}/kb/for-spenders")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "category"
    assert body["category"]["name"] == "For spenders"
    assert body["ancestors"] == []
    assert [
        (s["collection"]["name"], s["collection"]["articleCount"])
        for s in body["sections"]
    ] == [("Expenses", 1)]
    assert [a["title"] for a in body["articles"]] == ["Overview"]


async def test_the_kb_route_404s_on_a_path_that_names_nothing(
    client, db_session: AsyncSession
) -> None:
    workspace, _, _, _, _ = await _spenders_tree(db_session)

    response = await client.get(f"/api/public/{workspace.slug}/kb/for-spenders/nope")

    assert response.status_code == 404


async def test_an_article_names_who_wrote_it(
    client, db_session: AsyncSession
) -> None:
    """The byline under an article title. The real author, not a workspace-
    wide "written by" -- there is one on every article already."""
    workspace, category, article = await _published(db_session)

    response = await client.get(
        f"/api/public/{workspace.slug}/kb/{category.slug}/{article.slug}"
    )

    assert response.status_code == 200
    assert response.json()["article"]["author"] == {
        "name": "Nilesh Pant",
        "monogram": "NP",
    }


async def test_an_article_whose_author_is_gone_still_serves(
    client, db_session: AsyncSession
) -> None:
    """`author_user_id` is SET NULL when a user is deleted. The article
    outlives them, and the page has to render without a byline rather
    than 500."""
    workspace, category, article = await _published(db_session)
    article.author_user_id = None
    await db_session.flush()
    # The route reads through this same session, so the already-loaded
    # `author` relationship has to be re-read -- otherwise the article comes
    # back still carrying the author its FK no longer points at. `refresh`
    # rather than `expire`: expiring defers the reload to attribute access,
    # which lands outside the greenlet an async session needs for IO.
    await db_session.refresh(article, ["author"])

    response = await client.get(
        f"/api/public/{workspace.slug}/kb/{category.slug}/{article.slug}"
    )

    assert response.status_code == 200
    assert response.json()["article"]["author"] is None


async def test_a_search_result_carries_the_path_that_links_to_it(
    client, db_session: AsyncSession
) -> None:
    """A result is a link, and with a tree the caller cannot rebuild that
    link from a slug alone -- it would have to fetch and walk the whole
    index to find out where the article lives."""
    workspace, _, _, _, _ = await _spenders_tree(db_session)

    response = await client.get(
        f"/api/public/{workspace.slug}/kb/search", params={"q": "Body"}
    )

    assert response.status_code == 200
    # Sorted: search orders by rank, which is not this test's subject.
    assert sorted(a["path"] for a in response.json()) == [
        "for-spenders/expenses/add-a-receipt",
        "for-spenders/overview",
    ]


async def test_a_collection_page_carries_each_section_with_its_rows(
    db_session: AsyncSession,
) -> None:
    """A collection page draws a card per section, and each card lists that
    section's own rows -- its articles and its sub-collections. Fetching
    those per card would be a request per section for a page the tree in
    hand can already answer."""
    workspace = await make_workspace(db_session, slug="acme")
    author = await make_member(db_session, workspace, email="a@acme.dev")
    collection = await kb_categories.create(
        db_session, workspace.id, "For spenders", KbScope.external
    )
    section = await kb_categories.create(
        db_session, workspace.id, "Getting started", KbScope.external,
        parent_id=collection.id,
    )
    settings = await kb_categories.create(
        db_session, workspace.id, "Account settings", KbScope.external,
        parent_id=section.id,
    )
    await _publish_in(db_session, workspace, section, author, "First steps")
    await _publish_in(db_session, workspace, settings, author, "Change your email")

    found = await kb_public.resolve(db_session, workspace.id, ["for-spenders"])

    (only,) = found.sections
    assert only.category.name == "Getting started"
    assert [a.title for a in only.articles] == ["First steps"]
    assert [(c.name, n) for c, n in only.collections] == [("Account settings", 1)]
