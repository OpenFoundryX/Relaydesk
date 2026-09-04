"""Exercises migration 0007's ``direction`` backfill against real data.

``test_email_channel_models.py`` only ever constructs ``Message`` rows
*after* migration 0007 has already run, always passing ``direction``
explicitly. None of those tests touch the migration's own backfill logic --
the ``UPDATE messages SET direction = CASE WHEN role = 'customer' THEN
'inbound' ELSE 'outbound' END`` in 0007's ``upgrade()``. If that ``CASE
WHEN`` were ever replaced with a blanket ``server_default='outbound'``,
every test in that file would still pass, while every pre-existing seeded
customer message would be silently mislabelled as outbound.

This test stands up its own scratch database (never the shared
``relaydesk_test`` the rest of the suite migrates once per session and
which a downgrade here would break), inserts ``messages`` rows via raw SQL
at revision 0006 -- before ``direction`` exists -- then upgrades to 0007 and
asserts what the backfill actually produced.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import asyncpg
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from relaydesk.config import get_settings
from tests.conftest import API_ROOT

SCRATCH_DATABASE = "relaydesk_migration_test"


def _admin_url() -> sa.engine.URL:
    return sa.engine.make_url(get_settings().database_url)


async def _connect(database: str) -> asyncpg.Connection:
    url = _admin_url()
    return await asyncpg.connect(
        user=url.username,
        password=url.password,
        host=url.host,
        port=url.port or 5432,
        database=database,
    )


async def _recreate_scratch_database() -> None:
    connection = await _connect("postgres")
    try:
        await connection.execute(
            f'DROP DATABASE IF EXISTS "{SCRATCH_DATABASE}" WITH (FORCE)'
        )
        await connection.execute(f'CREATE DATABASE "{SCRATCH_DATABASE}"')
    finally:
        await connection.close()


async def _drop_scratch_database() -> None:
    connection = await _connect("postgres")
    try:
        await connection.execute(
            f'DROP DATABASE IF EXISTS "{SCRATCH_DATABASE}" WITH (FORCE)'
        )
    finally:
        await connection.close()


def _scratch_url() -> str:
    return _admin_url().set(database=SCRATCH_DATABASE).render_as_string(
        hide_password=False
    )


def _alembic_config() -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    config.attributes["sqlalchemy_url"] = _scratch_url()
    return config


async def _seed_pre_migration_messages() -> dict[str, uuid.UUID]:
    """Insert one customer and one agent message at revision 0006 -- before
    ``direction`` exists -- mirroring what a real pre-migration workspace
    would contain. Every column here is required at 0006 and has no server
    default, so each is supplied explicitly."""
    connection = await _connect(SCRATCH_DATABASE)
    try:
        workspace_id = uuid.uuid4()
        contact_id = uuid.uuid4()
        conversation_id = uuid.uuid4()
        customer_message_id = uuid.uuid4()
        agent_message_id = uuid.uuid4()
        now = datetime.now(UTC)

        await connection.execute(
            """
            INSERT INTO workspaces
                (id, name, slug, monogram, timezone, conversation_seq,
                 plan, trial_days_left, tickets_this_period, projected_tickets)
            VALUES ($1, 'Chronon', 'chronon', 'CH', 'UTC', 1, 'Starter', 0, 0, 0)
            """,
            workspace_id,
        )
        await connection.execute(
            """
            INSERT INTO contacts (id, workspace_id, email, name)
            VALUES ($1, $2, 'priya@northwind.io', 'Priya Raman')
            """,
            contact_id,
            workspace_id,
        )
        await connection.execute(
            """
            INSERT INTO conversations
                (id, workspace_id, number, subject, contact_id, channel,
                 status, priority, preview, last_message_at, unread,
                 summary_state)
            VALUES
                ($1, $2, 1, 'Checkout fails with a 402', $3, 'email', 'open',
                 'urgent', 'Every time I switch to annual billing...', $4,
                 false, 'none')
            """,
            conversation_id,
            workspace_id,
            contact_id,
            now,
        )
        await connection.execute(
            """
            INSERT INTO messages
                (id, workspace_id, conversation_id, role, author_name,
                 to_address, body, sent_at)
            VALUES ($1, $2, $3, 'customer', 'Priya Raman',
                    'support@chronon.co', 'Checkout fails', $4)
            """,
            customer_message_id,
            workspace_id,
            conversation_id,
            now,
        )
        await connection.execute(
            """
            INSERT INTO messages
                (id, workspace_id, conversation_id, role, author_name,
                 to_address, body, sent_at)
            VALUES ($1, $2, $3, 'agent', 'Nilesh Pant',
                    'priya@northwind.io', 'Looking into it', $4)
            """,
            agent_message_id,
            workspace_id,
            conversation_id,
            now + timedelta(minutes=1),
        )
        return {"customer": customer_message_id, "agent": agent_message_id}
    finally:
        await connection.close()


async def _read_directions(message_ids: dict[str, uuid.UUID]) -> dict[str, str]:
    connection = await _connect(SCRATCH_DATABASE)
    try:
        return {
            role: await connection.fetchval(
                "SELECT direction FROM messages WHERE id = $1", message_id
            )
            for role, message_id in message_ids.items()
        }
    finally:
        await connection.close()


async def test_migration_0007_backfills_direction_from_role() -> None:
    """The CASE WHEN backfill, exercised end to end on a scratch database.

    Would fail if 0007's ``direction`` column were populated with a blanket
    default instead of the role-derived backfill: the pre-existing customer
    message would then read back as ``outbound`` instead of ``inbound``.

    ``command.upgrade`` runs Alembic's async migrations by calling
    ``asyncio.run`` internally (see ``migrations/env.py``), which cannot be
    invoked from inside a running event loop. The rest of the suite runs
    under pytest-asyncio's session-scoped loop, so this test -- itself a
    coroutine on that same loop -- offloads each ``command.upgrade`` call to
    a worker thread via ``asyncio.to_thread``, giving Alembic a thread with
    no event loop of its own to start one in, rather than fighting the
    session loop directly.
    """
    await _recreate_scratch_database()
    try:
        config = _alembic_config()
        await asyncio.to_thread(command.upgrade, config, "0006")

        message_ids = await _seed_pre_migration_messages()

        await asyncio.to_thread(command.upgrade, config, "0007")

        directions = await _read_directions(message_ids)
    finally:
        await _drop_scratch_database()

    assert directions["customer"] == "inbound"
    assert directions["agent"] == "outbound"
