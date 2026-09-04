"""Operational commands.

``seed`` fills a development database with the demo workspace the console
was designed against. ``bootstrap`` is what a self-hoster runs once to
create their real workspace and first admin.
"""

import argparse
import asyncio
import os
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.db.session import async_session_factory
from relaydesk.errors import Conflict
from relaydesk.models import (
    ActivityEvent,
    ActivityKind,
    Channel,
    Contact,
    Conversation,
    ConversationLabel,
    ConversationStatus,
    Draft,
    Label,
    LabelColor,
    Membership,
    MembershipStatus,
    Message,
    MessageRole,
    Priority,
    Role,
    SavedView,
    User,
    Workspace,
)
from relaydesk.security.passwords import hash_password
from relaydesk.services import workspaces

# Read in preference to --password so the admin's password never lands in
# `ps` output or the shell history file.
ADMIN_PASSWORD_ENV = "RELAYDESK_ADMIN_PASSWORD"

# (subject, preview, contact_name, contact_email, channel, status, priority,
#  assignee: "admin" | "agent" | None, label_names, has_draft, minutes_ago)
DEMO_CONVERSATIONS = [
    (
        "Checkout fails with a 402 on annual plans",
        "Hey — every time I try to switch our workspace to annual billing the payment "
        "step returns a 402. Card works fine elsewhere.",
        "Priya Raman",
        "priya@northwind.io",
        Channel.email,
        ConversationStatus.open,
        Priority.urgent,
        None,
        ["Billing", "Bug"],
        True,
        12,
    ),
    (
        "How do I invite a read-only teammate?",
        "We want our finance lead to see invoices but not touch tickets. Is there a "
        "viewer role?",
        "Marcus Webb",
        "marcus@lattice-labs.com",
        Channel.portal,
        ConversationStatus.open,
        Priority.medium,
        "admin",
        ["Onboarding"],
        True,
        48,
    ),
    (
        "Discord bot stopped creating tickets last night",
        "Our forum channel was quiet in Relaydesk since about 23:00 UTC but there are "
        "definitely new threads.",
        "Ida Okonkwo",
        "ida@parsecgg.com",
        Channel.discord,
        ConversationStatus.open,
        Priority.high,
        "agent",
        ["Bug"],
        False,
        180,
    ),
    (
        "Request: bulk export of resolved tickets",
        "Would love a CSV export so we can run our own reporting on resolution times.",
        "Tomas Lind",
        "tomas@heliossoft.se",
        Channel.email,
        ConversationStatus.open,
        Priority.low,
        None,
        ["Feature request"],
        False,
        300,
    ),
    (
        "Refund for duplicate October charge",
        "We were billed twice on 3 Oct. Invoice numbers are INV-2291 and INV-2292.",
        "Grace Whitfield",
        "grace@bellcurve.app",
        Channel.email,
        ConversationStatus.pending,
        Priority.high,
        "admin",
        ["Billing"],
        False,
        1440,
    ),
    (
        "SAML metadata URL is rejected",
        "Okta gives us a metadata URL, but the field seems to want raw XML.",
        "Devon Ruiz",
        "devon@quorumhq.com",
        Channel.api,
        ConversationStatus.pending,
        Priority.medium,
        "agent",
        [],
        True,
        1500,
    ),
    (
        "Thanks — webhook signing sorted",
        "Rotating the secret did it. Appreciate the quick turnaround.",
        "Aiko Tanaka",
        "aiko@driftline.jp",
        Channel.email,
        ConversationStatus.resolved,
        Priority.low,
        "admin",
        [],
        False,
        2880,
    ),
    (
        "Password reset email never arrives",
        "Three of our users tried the reset link this morning and nothing landed, "
        "spam folder included.",
        "Owen Pryce",
        "owen@caldera.dev",
        Channel.portal,
        ConversationStatus.resolved,
        Priority.medium,
        "agent",
        ["Bug"],
        False,
        4320,
    ),
    (
        "Waiting on legal review of the DPA",
        "Our counsel is reviewing the data processing agreement. Nothing needed from "
        "you until they come back.",
        "Helena Marsh",
        "helena@ridgeway.co",
        Channel.email,
        ConversationStatus.on_hold,
        Priority.low,
        "admin",
        [],
        False,
        8640,
    ),
    (
        "Partnership opportunity for your team",
        "I help SaaS companies triple their pipeline. Do you have 15 minutes this "
        "week?",
        "Dana Voss",
        "dana@growthmail.biz",
        Channel.email,
        ConversationStatus.ignored,
        Priority.low,
        None,
        [],
        False,
        5760,
    ),
    (
        "test test test",
        "ignore this, testing the form",
        "Sam Rowe",
        "sam@example.com",
        Channel.portal,
        ConversationStatus.trash,
        Priority.low,
        None,
        [],
        False,
        11520,
    ),
]


async def seed(session: AsyncSession) -> None:
    """Idempotent: re-running leaves exactly one demo workspace."""
    existing = await session.scalar(
        sa.select(Workspace).where(Workspace.slug == "chronon")
    )
    if existing is not None:
        return

    workspace = Workspace(
        name="Chronon",
        slug="chronon",
        monogram="CH",
        timezone="Asia/Kolkata",
        plan="Starter",
        trial_days_left=6,
        tickets_this_period=412,
        projected_tickets=480,
    )
    session.add(workspace)
    await session.flush()
    await workspaces.create_default_channel_account(session, workspace.id)

    admin = User(
        email="nilesh@relaydesk.dev",
        name="Nilesh Pant",
        monogram="NP",
        timezone="Asia/Kolkata",
        password_hash=hash_password("relaydesk"),
    )
    agent = User(
        email="sara@relaydesk.dev",
        name="Sara Duval",
        monogram="SD",
        password_hash=hash_password("relaydesk"),
    )
    session.add_all([admin, agent])
    await session.flush()
    session.add_all(
        [
            Membership(
                workspace_id=workspace.id,
                user_id=admin.id,
                role=Role.admin,
                status=MembershipStatus.active,
            ),
            Membership(
                workspace_id=workspace.id,
                user_id=agent.id,
                role=Role.agent,
                status=MembershipStatus.active,
            ),
        ]
    )

    labels = {
        name: Label(workspace_id=workspace.id, name=name, color=color)
        for name, color in [
            ("Billing", LabelColor.amber),
            ("Bug", LabelColor.rose),
            ("Onboarding", LabelColor.citron),
            ("Feature request", LabelColor.sky),
        ]
    }
    session.add_all(labels.values())

    session.add_all(
        [
            SavedView(
                workspace_id=workspace.id,
                name="Urgent & unassigned",
                position=0,
                filters={
                    "priority": "urgent",
                    "assignee": "unassigned",
                    "status": "open",
                },
            ),
            SavedView(
                workspace_id=workspace.id,
                name="Assigned to me",
                position=1,
                filters={"assignee": "me"},
            ),
            SavedView(
                workspace_id=workspace.id,
                name="Waiting on customer",
                position=2,
                filters={"status": "pending"},
            ),
        ]
    )
    await session.flush()

    people = {"admin": admin, "agent": agent, None: None}
    now = datetime.now(UTC)

    for (
        subject,
        preview,
        contact_name,
        contact_email,
        channel,
        status,
        priority,
        assignee_key,
        label_names,
        has_draft,
        minutes_ago,
    ) in DEMO_CONVERSATIONS:
        contact = Contact(
            workspace_id=workspace.id, email=contact_email, name=contact_name
        )
        session.add(contact)
        await session.flush()

        workspace.conversation_seq += 1
        sent_at = now - timedelta(minutes=minutes_ago)
        assignee = people[assignee_key]
        conversation = Conversation(
            workspace_id=workspace.id,
            number=workspace.conversation_seq,
            subject=subject,
            contact_id=contact.id,
            channel=channel,
            status=status,
            priority=priority,
            assignee_id=assignee.id if assignee else None,
            preview=preview,
            last_message_at=sent_at,
            unread=status is ConversationStatus.open,
        )
        session.add(conversation)
        await session.flush()

        session.add(
            Message(
                workspace_id=workspace.id,
                conversation_id=conversation.id,
                role=MessageRole.customer,
                author_name=contact_name,
                to_address="support@chronon.co",
                body=preview,
                sent_at=sent_at,
            )
        )
        # One opening entry per thread, so the detail panel's History tab
        # has something in it on a fresh seed rather than reading empty.
        session.add(
            ActivityEvent(
                workspace_id=workspace.id,
                conversation_id=conversation.id,
                actor_user_id=admin.id,
                actor_name=admin.name,
                kind=ActivityKind.created,
                verb="opened this conversation via",
                value=channel.value,
                at=sent_at,
            )
        )
        for label_name in label_names:
            session.add(
                ConversationLabel(
                    conversation_id=conversation.id, label_id=labels[label_name].id
                )
            )
        if has_draft:
            first_name = contact_name.split()[0]
            session.add(
                Draft(
                    workspace_id=workspace.id,
                    conversation_id=conversation.id,
                    body=(
                        f"Hi {first_name},\n\nSorry to hear you're running into "
                        "trouble. Could you share a bit more detail so I can look "
                        "into this?\n\nThanks,\nRelaydesk Support"
                    ),
                )
            )

    await session.commit()


async def bootstrap(
    session: AsyncSession,
    workspace_name: str,
    admin_email: str,
    admin_name: str,
    admin_password: str,
) -> None:
    """Create the first workspace and its admin. Refuses if one exists."""
    existing = await session.scalar(sa.select(Workspace).limit(1))
    if existing is not None:
        raise Conflict("A workspace already exists; bootstrap is a one-time command.")

    slug = "".join(c if c.isalnum() else "-" for c in workspace_name.lower()).strip("-")
    workspace = Workspace(
        name=workspace_name,
        slug=slug or "workspace",
        monogram="".join(part[0] for part in workspace_name.split()[:2]).upper()
        or "WS",
    )
    user = User(
        email=admin_email,
        name=admin_name,
        monogram="".join(part[0] for part in admin_name.split()[:2]).upper() or "AD",
        password_hash=hash_password(admin_password),
    )
    session.add_all([workspace, user])
    await session.flush()
    await workspaces.create_default_channel_account(session, workspace.id)
    session.add(
        Membership(
            workspace_id=workspace.id,
            user_id=user.id,
            role=Role.admin,
            status=MembershipStatus.active,
        )
    )
    await session.commit()


def resolve_admin_password(cli_password: str | None) -> str | None:
    """Environment first, ``--password`` only as a fallback.

    A password passed in argv is visible to anyone who can run ``ps`` on the
    host and is written to the operator's shell history.
    """
    return os.environ.get(ADMIN_PASSWORD_ENV) or cli_password


def main() -> None:
    parser = argparse.ArgumentParser(prog="relaydesk")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("seed", help="Fill the database with demo data")
    boot = commands.add_parser("bootstrap", help="Create the first workspace and admin")
    boot.add_argument("--workspace", required=True)
    boot.add_argument("--email", required=True)
    boot.add_argument("--name", required=True)
    boot.add_argument(
        "--password",
        help=(
            "Admin password. Prefer the RELAYDESK_ADMIN_PASSWORD environment "
            "variable: a password in argv is visible in `ps` and shell history."
        ),
    )
    args = parser.parse_args()

    password = resolve_admin_password(getattr(args, "password", None))
    if args.command == "bootstrap" and not password:
        parser.error(
            f"Set {ADMIN_PASSWORD_ENV} in the environment, or pass --password."
        )

    async def run() -> None:
        async with async_session_factory() as session:
            if args.command == "seed":
                await seed(session)
            else:
                await bootstrap(
                    session,
                    workspace_name=args.workspace,
                    admin_email=args.email,
                    admin_name=args.name,
                    admin_password=password,
                )

    asyncio.run(run())


if __name__ == "__main__":
    main()
