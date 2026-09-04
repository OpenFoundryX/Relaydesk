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


def include_name(name: str | None, type_: str, parent_names: dict) -> bool:
    """Keep CHECK constraints out of autogenerate's comparison.

    The CHECK constraints behind ``sa.Enum(..., create_constraint=True)``
    are "type bound", and Alembic deliberately excludes those from the
    model side of the diff while still reflecting them from the database.
    Left alone, every one of them autogenerates as a spurious
    ``drop_constraint``. Migration 0006 owns them by explicit name; a slice
    that adds an enum value drops and recreates the constraint there.
    """
    return type_ != "check_constraint"


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
