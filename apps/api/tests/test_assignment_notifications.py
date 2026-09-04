import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.services import conversations, queue
from tests.factories import make_conversation, make_member, make_workspace


@pytest.fixture
def outbox(monkeypatch) -> list[dict]:
    sent: list[dict] = []

    def record(to: str, subject: str, text_body: str, html_body=None) -> None:
        sent.append({"to": to, "subject": subject, "text": text_body})

    monkeypatch.setattr(queue, "enqueue_system_email", record)
    return sent


async def test_assigning_to_someone_else_emails_them(
    db_session: AsyncSession, outbox: list[dict]
) -> None:
    workspace = await make_workspace(db_session)
    actor = await make_member(db_session, workspace, email="nilesh@example.com")
    other = await make_member(db_session, workspace, email="sara@example.com")
    conversation = await make_conversation(db_session, workspace, subject="Refund")

    await conversations.set_assignee(
        db_session, workspace.id, conversation.id, other.id, actor
    )

    assert len(outbox) == 1
    assert outbox[0]["to"] == "sara@example.com"
    assert "Refund" in outbox[0]["subject"]


async def test_assigning_to_yourself_emails_nobody(
    db_session: AsyncSession, outbox: list[dict]
) -> None:
    """Picking a ticket up off the queue is the most common assignment there
    is, and mailing yourself about it is noise."""
    workspace = await make_workspace(db_session)
    actor = await make_member(db_session, workspace, email="nilesh@example.com")
    conversation = await make_conversation(db_session, workspace)

    await conversations.set_assignee(
        db_session, workspace.id, conversation.id, actor.id, actor
    )

    assert outbox == []


async def test_the_preference_is_honoured(
    db_session: AsyncSession, outbox: list[dict]
) -> None:
    workspace = await make_workspace(db_session)
    actor = await make_member(db_session, workspace, email="nilesh@example.com")
    other = await make_member(db_session, workspace, email="sara@example.com")
    other.notify_on_assignment = False
    await db_session.flush()
    conversation = await make_conversation(db_session, workspace)

    await conversations.set_assignee(
        db_session, workspace.id, conversation.id, other.id, actor
    )

    assert outbox == []


async def test_unassigning_emails_nobody(
    db_session: AsyncSession, outbox: list[dict]
) -> None:
    workspace = await make_workspace(db_session)
    actor = await make_member(db_session, workspace, email="nilesh@example.com")
    other = await make_member(db_session, workspace, email="sara@example.com")
    conversation = await make_conversation(db_session, workspace)
    await conversations.set_assignee(
        db_session, workspace.id, conversation.id, other.id, actor
    )
    outbox.clear()

    await conversations.set_assignee(
        db_session, workspace.id, conversation.id, None, actor
    )

    assert outbox == []


async def test_patch_me_toggles_the_preference(db_session, client) -> None:
    from tests.factories import sign_in

    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace, email="nilesh@example.com")
    await db_session.commit()
    headers = await sign_in(client, db_session, user.email)

    response = await client.patch(
        "/api/auth/me", json={"notifyOnAssignment": False}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["user"]["notifyOnAssignment"] is False
