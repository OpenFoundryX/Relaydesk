import hashlib
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.config import get_settings
from relaydesk.email_parse.normalize import ParsedAttachment
from relaydesk.errors import NotFound
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


async def test_the_download_route_needs_a_session(db_session, client) -> None:
    workspace = await make_workspace(db_session, slug="acme")
    message = await _message(db_session, workspace)
    stored = await attachments.store(db_session, message, [_parsed()])
    await db_session.commit()

    response = await client.get(f"/api/attachments/{stored[0].id}")

    assert response.status_code == 401
