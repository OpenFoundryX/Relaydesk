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


async def test_the_index_lists_published_external_articles(
    db_session: AsyncSession,
) -> None:
    workspace, _, _ = await _published(db_session)

    rows = await kb_public.index(db_session, workspace.id)

    assert [(c.name, [a.title for a in arts]) for c, arts in rows] == [
        ("Billing", ["Refunds"])
    ]


async def test_a_draft_never_appears_publicly(db_session: AsyncSession) -> None:
    workspace, _, _ = await _published(db_session, status=ArticleStatus.draft)

    assert await kb_public.index(db_session, workspace.id) == []


async def test_a_ready_article_is_not_public_either(db_session: AsyncSession) -> None:
    """Ready means reviewed, not live. Publishing is a separate decision."""
    workspace, _, _ = await _published(db_session, status=ArticleStatus.ready)

    assert await kb_public.index(db_session, workspace.id) == []


async def test_internal_articles_are_never_public(db_session: AsyncSession) -> None:
    """These are the agent's runbooks. Publishing one would expose internal
    procedure to customers."""
    workspace, _, _ = await _published(db_session, scope=KbScope.internal)

    assert await kb_public.index(db_session, workspace.id) == []


async def test_an_empty_category_is_omitted_from_the_index(
    db_session: AsyncSession,
) -> None:
    workspace, _, _ = await _published(db_session)
    await kb_categories.create(db_session, workspace.id, "Returns", KbScope.external)

    rows = await kb_public.index(db_session, workspace.id)

    assert [c.name for c, _ in rows] == ["Billing"]


async def test_an_article_is_readable_by_its_slugs(db_session: AsyncSession) -> None:
    workspace, category, article = await _published(db_session)

    found = await kb_public.article(
        db_session, workspace.id, category.slug, article.slug
    )

    assert found.id == article.id


async def test_an_unpublished_article_is_a_404_not_a_403(
    db_session: AsyncSession,
) -> None:
    """403 would confirm that an article exists at a guessable slug."""
    workspace, category, article = await _published(
        db_session, status=ArticleStatus.draft
    )

    with pytest.raises(NotFound):
        await kb_public.article(db_session, workspace.id, category.slug, article.slug)


async def test_another_workspaces_article_is_not_readable(
    db_session: AsyncSession,
) -> None:
    theirs, category, article = await _published(db_session, slug="theirs")
    mine = await make_workspace(db_session, slug="mine")

    with pytest.raises(NotFound):
        await kb_public.article(db_session, mine.id, category.slug, article.slug)


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

    assert await kb_public.index(db_session, workspace.id) == []
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


async def test_the_index_route_lists_published_external_articles(
    client, db_session: AsyncSession
) -> None:
    workspace, _, _ = await _published(db_session)

    response = await client.get(f"/api/public/{workspace.slug}/kb")

    assert response.status_code == 200
    body = response.json()
    assert [c["name"] for c in body] == ["Billing"]
    assert [a["title"] for a in body[0]["articles"]] == ["Refunds"]


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
    assert response.json()["title"] == "Refunds"


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
