from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models import (
    Channel,
    Contact,
    Conversation,
    ConversationStatus,
    Draft,
    Label,
    Membership,
    MembershipStatus,
    Message,
    MessageDirection,
    MessageRole,
    Priority,
    Role,
    User,
    Workspace,
)
from relaydesk.security.passwords import hash_password


async def make_workspace(session: AsyncSession, slug: str = "chronon") -> Workspace:
    workspace = Workspace(name=slug.title(), slug=slug, monogram=slug[:2].upper())
    session.add(workspace)
    await session.flush()
    return workspace


async def make_member(
    session: AsyncSession,
    workspace: Workspace,
    email: str = "nilesh@relaydesk.dev",
    name: str = "Nilesh Pant",
    role: Role = Role.admin,
    password: str = "relaydesk",
    user: User | None = None,
) -> User:
    if user is None:
        user = User(
            email=email,
            name=name,
            monogram="".join(p[0] for p in name.split()[:2]).upper(),
            password_hash=hash_password(password),
        )
        session.add(user)
        await session.flush()
    session.add(
        Membership(
            workspace_id=workspace.id,
            user_id=user.id,
            role=role,
            status=MembershipStatus.active,
            # Explicit, not the server default: everything in a test runs
            # inside one outer transaction (see conftest's ``db_session``),
            # and Postgres's ``now()`` is fixed for the whole transaction —
            # two memberships created back-to-back in the same test would
            # otherwise get an identical ``created_at``, which is exactly
            # the ordering ``default_membership`` needs to disambiguate.
            created_at=datetime.now(UTC),
        )
    )
    await session.flush()
    return user


async def make_conversation(
    session: AsyncSession,
    workspace: Workspace,
    *,
    subject: str = "Checkout fails with a 402",
    status: ConversationStatus = ConversationStatus.open,
    priority: Priority = Priority.urgent,
    assignee: User | None = None,
    minutes_ago: int = 12,
    with_draft: bool = False,
    contact_email: str = "priya@northwind.io",
    contact_name: str = "Priya Raman",
) -> Conversation:
    # Contacts are unique per (workspace, email), so reuse one when it exists.
    # Several tests create two conversations in one workspace.
    contact = await session.scalar(
        sa.select(Contact).where(
            Contact.workspace_id == workspace.id, Contact.email == contact_email
        )
    )
    if contact is None:
        contact = Contact(
            workspace_id=workspace.id, email=contact_email, name=contact_name
        )
        session.add(contact)
        await session.flush()

    workspace.conversation_seq += 1
    sent_at = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    conversation = Conversation(
        workspace_id=workspace.id,
        number=workspace.conversation_seq,
        subject=subject,
        contact_id=contact.id,
        channel=Channel.email,
        status=status,
        priority=priority,
        assignee_id=assignee.id if assignee else None,
        preview="Every time I switch to annual billing the payment step returns a 402.",
        last_message_at=sent_at,
    )
    session.add(conversation)
    await session.flush()

    session.add(
        Message(
            workspace_id=workspace.id,
            conversation_id=conversation.id,
            role=MessageRole.customer,
            direction=MessageDirection.inbound,
            author_name=contact.name,
            to_address="support@chronon.co",
            body=conversation.preview,
            sent_at=sent_at,
        )
    )
    if with_draft:
        session.add(
            Draft(
                workspace_id=workspace.id,
                conversation_id=conversation.id,
                body="Hi Priya,\n\nSorry about that.",
            )
        )
    await session.commit()
    return conversation


async def make_label(
    session: AsyncSession, workspace: Workspace, name: str = "Billing"
) -> Label:
    label = Label(workspace_id=workspace.id, name=name)
    session.add(label)
    await session.commit()
    return label


async def sign_in(
    client, session: AsyncSession, user_email: str, password: str = "relaydesk"
) -> dict:
    response = await client.post(
        "/api/auth/login", json={"email": user_email, "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}
