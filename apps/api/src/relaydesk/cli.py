"""Operational commands.

``seed`` fills a development database with the demo workspace the console
was designed against. ``bootstrap`` is what a self-hoster runs once to
create their real workspace and first admin.
"""

import argparse
import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.db.session import async_session_factory
from relaydesk.email_parse import normalize
from relaydesk.errors import Conflict, NotFound
from relaydesk.models import (
    ActivityEvent,
    ActivityKind,
    Channel,
    Contact,
    ConversationLabel,
    ConversationStatus,
    Draft,
    Label,
    LabelColor,
    Membership,
    MembershipStatus,
    MessageDirection,
    MessageRole,
    Priority,
    RawMessage,
    RawMessageState,
    Role,
    SavedView,
    User,
    Workspace,
)
from relaydesk.security.passwords import hash_password
from relaydesk.services import conversations, workspaces

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

    workspace = await workspaces.create_workspace(
        session,
        name="Chronon",
        slug="chronon",
        monogram="CH",
        timezone="Asia/Kolkata",
        plan="Starter",
        trial_days_left=6,
        tickets_this_period=412,
        projected_tickets=480,
    )

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

        sent_at = now - timedelta(minutes=minutes_ago)
        assignee = people[assignee_key]
        conversation = await conversations.create_conversation(
            session, workspace.id, contact, subject, channel, sent_at
        )
        # create_conversation always opens unread; the demo data wants a mix
        # so the console shows what a read, resolved ticket looks like too.
        conversation.status = status
        conversation.priority = priority
        conversation.assignee_id = assignee.id if assignee else None
        conversation.unread = status is ConversationStatus.open

        await conversations.append_message(
            session,
            conversation,
            role=MessageRole.customer,
            direction=MessageDirection.inbound,
            author_name=contact_name,
            to_address="support@chronon.co",
            body=preview,
            sent_at=sent_at,
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

    # create_conversation allocates the sequence with a raw UPDATE, which
    # bypasses the ORM's in-memory attribute on ``workspace`` -- refresh it
    # so the object this function was handed reflects the final count.
    await session.refresh(workspace, ["conversation_seq"])
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
    workspace = await workspaces.create_workspace(
        session,
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
    session.add(user)
    await session.flush()
    session.add(
        Membership(
            workspace_id=workspace.id,
            user_id=user.id,
            role=Role.admin,
            status=MembershipStatus.active,
        )
    )
    await session.commit()


async def unrouted(session: AsyncSession, limit: int = 20) -> list[RawMessage]:
    """List mail this deployment could not turn into a ticket.

    Most of these matched no workspace at all -- usually a forwarding rule
    pointing at the wrong address. A few routed fine but are a bounce that
    could not be threaded to any conversation (state is `unrouted` either
    way; see `_handle_bounce`). The bytes are kept for both, so fixing the
    rule and re-running ``relaydesk reingest <id>`` turns these into tickets
    rather than losing them.
    """
    return list(
        await session.scalars(
            sa.select(RawMessage)
            .where(RawMessage.state == RawMessageState.unrouted)
            .order_by(RawMessage.received_at.desc())
            .limit(limit)
        )
    )


def _print_unrouted(rows: list[RawMessage]) -> None:
    if not rows:
        print("No unrouted mail.")
        return
    for row in rows:
        # This listing is the operator's tool for diagnosing broken mail, so
        # one message this deployment's own parser chokes on (it otherwise
        # never raises, but the bytes are attacker-controlled) must not hide
        # every other row in the listing.
        try:
            message = normalize.parse(row.raw)
            detail = f"from={message.from_email!r}  subject={message.subject!r}"
        except Exception:
            detail = "(unparseable)"
        print(f"{row.id}  {row.received_at.isoformat()}  {detail}")


async def reingest(session: AsyncSession, raw_message_id: uuid.UUID) -> None:
    """Reset a stuck (usually unrouted) message and re-enqueue it.

    Imported lazily: importing the Celery task at module scope would pull
    the worker app into every ``relaydesk`` CLI invocation, including ones
    that never touch it.
    """
    from relaydesk.worker.tasks.inbound import ingest_message

    row = await session.get(RawMessage, raw_message_id)
    if row is None:
        raise NotFound("That raw message does not exist.")
    row.state = RawMessageState.fetched
    await session.commit()
    ingest_message.delay(str(row.id))


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
    unrouted_parser = commands.add_parser(
        "unrouted", help="List mail this deployment could not turn into a ticket"
    )
    unrouted_parser.add_argument("--limit", type=int, default=20)
    reingest_parser = commands.add_parser(
        "reingest", help="Reset a raw message to fetched and re-enqueue it"
    )
    reingest_parser.add_argument("raw_message_id", type=uuid.UUID)
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
            elif args.command == "bootstrap":
                await bootstrap(
                    session,
                    workspace_name=args.workspace,
                    admin_email=args.email,
                    admin_name=args.name,
                    admin_password=password,
                )
            elif args.command == "unrouted":
                _print_unrouted(await unrouted(session, args.limit))
            elif args.command == "reingest":
                await reingest(session, args.raw_message_id)
            else:
                # Unreachable: `add_subparsers(required=True)` above already
                # restricts `args.command` to the four branches above. Kept
                # explicit rather than trailing on the last `elif` so a fifth
                # subcommand added later can't silently fall through here.
                parser.error(f"Unknown command: {args.command!r}")

    asyncio.run(run())


if __name__ == "__main__":
    main()
