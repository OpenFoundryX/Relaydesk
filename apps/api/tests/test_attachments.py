import hashlib
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.config import get_settings
from relaydesk.email_parse.normalize import ParsedAttachment
from relaydesk.errors import NotFound
from relaydesk.models.attachment import Attachment
from relaydesk.models.message import MessageDirection, MessageRole
from relaydesk.services import attachments, conversations
from tests.factories import make_conversation, make_member, make_workspace, sign_in


@pytest.fixture(autouse=True)
def attachment_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "attachment_dir", str(tmp_path))
    return tmp_path


def _parsed(name="invoice.pdf", content=b"%PDF fake", ctype="application/pdf"):
    return ParsedAttachment(
        filename=name,
        content_type=ctype,
        content=content,
        inline=False,
        content_id=None,
    )


async def _message(session, workspace):
    conversation = await make_conversation(session, workspace)
    return await conversations.append_message(
        session,
        conversation,
        role=MessageRole.customer,
        direction=MessageDirection.inbound,
        author_name="Ada",
        body="See attached",
        sent_at=conversation.last_message_at,
    )


async def test_content_is_addressed_by_hash_not_by_filename(
    db_session: AsyncSession, attachment_dir: Path
) -> None:
    """The sender chooses the filename. Writing to it would be a path
    traversal; writing to its hash cannot be."""
    workspace = await make_workspace(db_session)
    message = await _message(db_session, workspace)

    stored = await attachments.store(db_session, message, [_parsed()])

    digest = hashlib.sha256(b"%PDF fake").hexdigest()
    assert stored[0].sha256 == digest
    assert stored[0].storage_key.endswith(digest)
    assert (attachment_dir / str(workspace.id) / digest).read_bytes() == b"%PDF fake"
    assert stored[0].filename == "invoice.pdf"


async def test_identical_files_are_stored_once(
    db_session: AsyncSession, attachment_dir: Path
) -> None:
    workspace = await make_workspace(db_session)
    first = await _message(db_session, workspace)
    second = await _message(db_session, workspace)

    await attachments.store(db_session, first, [_parsed()])
    await attachments.store(db_session, second, [_parsed()])

    digest = hashlib.sha256(b"%PDF fake").hexdigest()
    files = list((attachment_dir / str(workspace.id)).iterdir())
    assert [f.name for f in files] == [digest]


async def test_the_size_cap_stops_at_the_limit(
    db_session: AsyncSession, monkeypatch
) -> None:
    """Past the cap the remaining parts are skipped and the body still
    ingests — a huge attachment must not cost the ticket."""
    monkeypatch.setattr(get_settings(), "attachment_max_bytes", 10)
    workspace = await make_workspace(db_session)
    message = await _message(db_session, workspace)

    stored = await attachments.store(
        db_session,
        message,
        [
            _parsed(name="small.txt", content=b"12345"),
            _parsed(name="big.bin", content=b"x" * 50),
        ],
    )

    assert [a.filename for a in stored] == ["small.txt"]


def test_only_images_keep_their_content_type() -> None:
    """An inbound .html served inline from our own origin is stored XSS."""
    assert attachments.safe_content_type("image/png") == "image/png"
    assert attachments.safe_content_type("text/html") == "application/octet-stream"
    assert (
        attachments.safe_content_type("image/svg+xml") == "application/octet-stream"
    )
    assert (
        attachments.safe_content_type("application/pdf") == "application/octet-stream"
    )


async def test_another_workspace_gets_a_404(db_session: AsyncSession) -> None:
    mine = await make_workspace(db_session, slug="acme")
    theirs = await make_workspace(db_session, slug="other")
    message = await _message(db_session, mine)
    stored = await attachments.store(db_session, message, [_parsed()])

    with pytest.raises(NotFound):
        await attachments.read(db_session, theirs.id, stored[0].id)


async def test_a_malformed_storage_key_cannot_escape_the_workspace_directory(
    db_session: AsyncSession,
) -> None:
    """storage_key is no longer read at all: the path is rebuilt from
    workspace_id and sha256 (see attachments.read). This pins that a
    hostile storage_key -- a bad migration, a manual edit, a second writer
    -- has no effect, because the column is simply never consulted, not
    because anything validates it. It does NOT exercise the containment
    check itself; see
    test_a_hostile_sha256_cannot_escape_the_workspace_directory for that,
    which drives a hostile value through sha256, the field the path is
    actually built from."""
    workspace = await make_workspace(db_session)
    message = await _message(db_session, workspace)
    await attachments.store(db_session, message, [_parsed()])
    row = Attachment(
        workspace_id=workspace.id,
        message_id=message.id,
        filename="passwd",
        content_type="text/plain",
        size_bytes=0,
        sha256="deadbeef",
        storage_key="../../../../../../../../etc/passwd",
        inline=False,
        content_id=None,
    )
    db_session.add(row)
    await db_session.flush()

    with pytest.raises(NotFound):
        await attachments.read(db_session, workspace.id, row.id)


async def test_a_hostile_sha256_cannot_escape_the_workspace_directory(
    db_session: AsyncSession,
) -> None:
    """sha256 -- not storage_key -- is what the read path is actually built
    from (`_root() / str(workspace_id) / row.sha256`), so it is the real
    attack surface. A row whose sha256 is a traversal sequence must still
    404 rather than resolve outside the workspace's directory. The
    workspace directory must already exist for the traversal to resolve at
    all against a real file, which is why a legitimate attachment is
    stored first."""
    workspace = await make_workspace(db_session)
    message = await _message(db_session, workspace)
    await attachments.store(db_session, message, [_parsed()])
    row = Attachment(
        workspace_id=workspace.id,
        message_id=message.id,
        filename="passwd",
        content_type="text/plain",
        size_bytes=0,
        sha256="../../../../../../../../etc/passwd",
        storage_key="irrelevant",
        inline=False,
        content_id=None,
    )
    db_session.add(row)
    await db_session.flush()

    with pytest.raises(NotFound):
        await attachments.read(db_session, workspace.id, row.id)


async def test_identical_bytes_in_different_workspaces_stay_separate(
    db_session: AsyncSession, attachment_dir: Path
) -> None:
    workspace_a = await make_workspace(db_session, slug="acme")
    workspace_b = await make_workspace(db_session, slug="other")
    message_a = await _message(db_session, workspace_a)
    message_b = await _message(db_session, workspace_b)

    stored_a = await attachments.store(db_session, message_a, [_parsed()])
    stored_b = await attachments.store(db_session, message_b, [_parsed()])

    digest = hashlib.sha256(b"%PDF fake").hexdigest()
    assert (attachment_dir / str(workspace_a.id) / digest).is_file()
    assert (attachment_dir / str(workspace_b.id) / digest).is_file()

    _, content_a = await attachments.read(db_session, workspace_a.id, stored_a[0].id)
    _, content_b = await attachments.read(db_session, workspace_b.id, stored_b[0].id)
    assert content_a == b"%PDF fake"
    assert content_b == b"%PDF fake"

    # Each workspace can only read its own row -- not the other's, even
    # though the bytes are identical.
    with pytest.raises(NotFound):
        await attachments.read(db_session, workspace_a.id, stored_b[0].id)


async def test_the_download_route_forces_a_download(db_session, client) -> None:
    workspace = await make_workspace(db_session, slug="acme")
    member = await make_member(db_session, workspace, email="nilesh@example.com")
    message = await _message(db_session, workspace)
    stored = await attachments.store(db_session, message, [_parsed()])
    await db_session.commit()
    headers = await sign_in(client, db_session, member.email)

    response = await client.get(f"/api/attachments/{stored[0].id}", headers=headers)

    assert response.status_code == 200
    assert response.content == b"%PDF fake"
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["x-content-type-options"] == "nosniff"


async def test_the_download_route_serves_a_non_latin1_filename(
    db_session, client
) -> None:
    """Starlette encodes response headers as latin-1, so a plain
    ``filename="..."`` carrying a CJK, Cyrillic, or Greek character (or an
    emoji) would 500 the whole download -- ordinary international support
    mail, not an edge case. RFC 5987's ``filename*`` form must carry the
    real UTF-8 name, with an ASCII-safe ``filename=`` alongside it for a
    client that only understands that form."""
    workspace = await make_workspace(db_session, slug="acme")
    member = await make_member(db_session, workspace, email="nilesh@example.com")
    message = await _message(db_session, workspace)
    stored = await attachments.store(
        db_session, message, [_parsed(name="请款单.pdf")]
    )
    await db_session.commit()
    headers = await sign_in(client, db_session, member.email)

    response = await client.get(f"/api/attachments/{stored[0].id}", headers=headers)

    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert "filename*=UTF-8''%E8%AF%B7%E6%AC%BE%E5%8D%95.pdf" in disposition
    assert 'filename="' in disposition


async def test_the_download_route_needs_a_session(db_session, client) -> None:
    workspace = await make_workspace(db_session, slug="acme")
    message = await _message(db_session, workspace)
    stored = await attachments.store(db_session, message, [_parsed()])
    await db_session.commit()

    response = await client.get(f"/api/attachments/{stored[0].id}")

    assert response.status_code == 401


async def test_a_skipped_attachment_is_logged(
    db_session: AsyncSession, monkeypatch, caplog
) -> None:
    """Skipping is right for inbound mail -- it has already been accepted by
    the time it reaches here and cannot be refused after the fact -- but it
    is a silent partial loss, and silent is the part that has to go. A
    caller that can still refuse the whole submission does not rely on
    this: `tickets.validate` checks the same shared budget up front, so
    nothing from the portal ever reaches this branch.
    """
    import logging

    monkeypatch.setattr(get_settings(), "attachment_max_bytes", 10)
    # See tests/test_queue.py: migrations/env.py's fileConfig() disables
    # every logger that existed at that point, this module's included.
    monkeypatch.setattr(attachments.logger, "disabled", False)
    workspace = await make_workspace(db_session)
    message = await _message(db_session, workspace)

    with caplog.at_level(logging.WARNING):
        stored = await attachments.store(
            db_session,
            message,
            [_parsed(name="huge.bin", content=b"x" * 50)],
        )

    assert stored == []
    assert "huge.bin" in caplog.text
