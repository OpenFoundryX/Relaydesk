from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from relaydesk.config import get_settings
from relaydesk.models import Base  # noqa: F401  (imports every model)

config = context.config
config.set_main_option(
    "sqlalchemy.url",
    config.attributes.get("sqlalchemy_url") or get_settings().database_url,
)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# The CHECK constraints behind ``sa.Enum(..., create_constraint=True)`` are
# "type bound": Alembic reflects them from the database but
# ``sqla_compat.all_table_check_constraints()`` excludes them from the model
# side of the diff, so each would autogenerate as a spurious
# ``drop_constraint``. Migration 0006 owns exactly these ten by name.
#
# THIS LIST IS EXHAUSTIVE AND MUST STAY THAT WAY. Every other CHECK
# constraint is compared normally: a hand-written ``CheckConstraint`` on a
# model, or one that has drifted into the database on its own, is still
# reported. If you add a non-enum CHECK constraint, do NOT add it here —
# hiding it would make real drift invisible. If you add an enum *value*,
# note that widening one of the constraints below is invisible to
# autogenerate either way (the model side of a type-bound constraint is
# never compared), so the migration must drop and recreate it by name —
# which is why they are named predictably.
ENUM_CHECK_CONSTRAINTS = frozenset(
    {
        "ck_activity_events_kind",
        "ck_conversations_channel",
        "ck_conversations_priority",
        "ck_conversations_status",
        "ck_conversations_summary_state",
        "ck_invites_role",
        "ck_labels_color",
        "ck_memberships_role",
        "ck_memberships_status",
        "ck_messages_role",
    }
)


def include_name(name: str | None, type_: str, parent_names: dict) -> bool:
    if type_ == "check_constraint":
        return name not in ENUM_CHECK_CONSTRAINTS
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        include_name=include_name,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: object) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    import asyncio

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
