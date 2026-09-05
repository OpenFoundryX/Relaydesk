import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.config import get_settings
from relaydesk.errors import Invalid, NotFound
from relaydesk.models.kb import KbScope
from relaydesk.services import kb_articles, kb_categories, kb_images
from tests.factories import make_member, make_workspace, sign_in

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


@pytest.fixture(autouse=True)
def image_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "attachment_dir", str(tmp_path))
    return tmp_path


async def _article(session, *, slug="chronon"):
    workspace = await make_workspace(session, slug=slug)
    author = await make_member(session, workspace, email=f"a@{slug}.dev")
    category = await kb_categories.create(
        session, workspace.id, "Billing", KbScope.external
    )
    article = await kb_articles.create(
        session, workspace.id, category.id, "Refunds", author
    )
    return workspace, author, article


async def test_an_image_is_stored_content_addressed(db_session: AsyncSession) -> None:
    workspace, _, article = await _article(db_session)

    image = await kb_images.store(
        db_session, article, "screenshot.png", "image/png", PNG
    )

    assert image.article_id == article.id
    assert image.workspace_id == workspace.id
    assert image.storage_key.endswith(image.sha256)
    assert image.size_bytes == len(PNG)


async def test_reading_returns_the_bytes(db_session: AsyncSession) -> None:
    workspace, _, article = await _article(db_session)
    image = await kb_images.store(
        db_session, article, "screenshot.png", "image/png", PNG
    )

    row, content = await kb_images.read(db_session, workspace.id, image.id)

    assert content == PNG
    assert row.filename == "screenshot.png"


async def test_another_workspaces_image_is_a_404(db_session: AsyncSession) -> None:
    mine, _, article = await _article(db_session, slug="mine")
    theirs, _, _ = await _article(db_session, slug="theirs")
    image = await kb_images.store(db_session, article, "s.png", "image/png", PNG)

    with pytest.raises(NotFound):
        await kb_images.read(db_session, theirs.id, image.id)


async def test_a_non_image_upload_is_refused(db_session: AsyncSession) -> None:
    """This route exists to put pictures in articles. Anything else would be
    an unauthenticated file host once the article is published."""
    _, _, article = await _article(db_session)

    with pytest.raises(Invalid):
        await kb_images.store(
            db_session, article, "payload.html", "text/html", b"<script>"
        )


async def test_svg_is_refused(db_session: AsyncSession) -> None:
    """SVG executes script when rendered inline, and an article image is
    rendered inline by definition."""
    _, _, article = await _article(db_session)

    with pytest.raises(Invalid):
        await kb_images.store(
            db_session, article, "logo.svg", "image/svg+xml", b"<svg/>"
        )


async def test_an_oversized_image_is_refused(
    db_session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(get_settings(), "kb_image_max_bytes", 16)
    _, _, article = await _article(db_session)

    with pytest.raises(Invalid):
        await kb_images.store(db_session, article, "big.png", "image/png", b"x" * 32)


async def test_a_zero_byte_image_is_stored(db_session: AsyncSession) -> None:
    """Pinning current behaviour, not endorsing it: nothing in `store`
    refuses an empty file, so this documents that rather than changing it."""
    _, _, article = await _article(db_session)

    image = await kb_images.store(db_session, article, "empty.png", "image/png", b"")

    assert image.size_bytes == 0


async def test_deleting_an_article_removes_its_image_rows(
    db_session: AsyncSession,
) -> None:
    workspace, _, article = await _article(db_session)
    image = await kb_images.store(db_session, article, "s.png", "image/png", PNG)
    await db_session.flush()

    await kb_articles.delete(db_session, workspace.id, article.id)

    with pytest.raises(NotFound):
        await kb_images.read(db_session, workspace.id, image.id)


async def test_the_upload_route_returns_an_id_and_url(db_session, client) -> None:
    workspace, author, article = await _article(db_session)
    await db_session.commit()
    headers = await sign_in(client, db_session, author.email)

    response = await client.post(
        f"/api/kb/articles/{article.id}/images",
        files={"file": ("screenshot.png", PNG, "image/png")},
        headers=headers,
    )

    assert response.status_code == 201
    assert response.json()["url"].startswith("/api/kb/images/")


async def test_the_upload_route_rejects_an_oversized_file_before_reading_it(
    db_session, client, monkeypatch
) -> None:
    """The route consults the declared size before it ever calls
    `file.read()`. Patching `read` to explode proves it: if the early check
    were removed, the route would call the patched method and this request
    would fail with the patched error instead of a clean 422.
    """
    from starlette.datastructures import UploadFile

    async def _must_not_be_called(self, *args, **kwargs):
        raise AssertionError("file.read() must not run for an oversized upload")

    monkeypatch.setattr(UploadFile, "read", _must_not_be_called)
    monkeypatch.setattr(get_settings(), "kb_image_max_bytes", 16)

    workspace, author, article = await _article(db_session)
    await db_session.commit()
    headers = await sign_in(client, db_session, author.email)

    response = await client.post(
        f"/api/kb/articles/{article.id}/images",
        files={"file": ("big.png", b"x" * 32, "image/png")},
        headers=headers,
    )

    assert response.status_code == 422


async def test_the_download_route_serves_an_image_inline(db_session, client) -> None:
    workspace, author, article = await _article(db_session)
    image = await kb_images.store(db_session, article, "s.png", "image/png", PNG)
    await db_session.commit()
    headers = await sign_in(client, db_session, author.email)

    response = await client.get(f"/api/kb/images/{image.id}", headers=headers)

    assert response.status_code == 200
    assert response.content == PNG
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"
