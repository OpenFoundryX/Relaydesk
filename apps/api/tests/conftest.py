from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import asyncpg
import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from relaydesk.config import get_settings
from relaydesk.db.session import get_session
from relaydesk.main import app

API_ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE = "relaydesk_test"


def _test_url() -> str:
    url = sa.engine.make_url(get_settings().database_url)
    return url.set(database=TEST_DATABASE).render_as_string(hide_password=False)


async def _recreate_database() -> None:
    url = sa.engine.make_url(get_settings().database_url)
    connection = await asyncpg.connect(
        user=url.username,
        password=url.password,
        host=url.host,
        port=url.port or 5432,
        database="postgres",
    )
    try:
        await connection.execute(
            f'DROP DATABASE IF EXISTS "{TEST_DATABASE}" WITH (FORCE)'
        )
        await connection.execute(f'CREATE DATABASE "{TEST_DATABASE}"')
    finally:
        await connection.close()


@pytest.fixture(scope="session")
def migrated_database() -> Iterator[str]:
    """Drop, recreate, and migrate the test database once per session.

    Running Alembic rather than ``create_all`` means the migrations
    themselves are what the suite exercises.
    """
    import asyncio

    asyncio.run(_recreate_database())

    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    config.attributes["sqlalchemy_url"] = _test_url()
    command.upgrade(config, "head")

    yield _test_url()


@pytest.fixture(scope="session")
async def engine(migrated_database: str):
    engine = create_async_engine(migrated_database, pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(engine) -> AsyncIterator[AsyncSession]:
    """A session whose writes are rolled back after each test.

    ``join_transaction_mode="create_savepoint"`` lets service code call
    ``commit()`` normally while the outer transaction still rolls back.
    """
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[get_session] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    app.dependency_overrides.clear()
