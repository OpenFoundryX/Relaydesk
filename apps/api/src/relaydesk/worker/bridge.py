"""Synchronous Celery, asynchronous everything else.

Celery tasks are synchronous functions, but every service in this codebase is
``async def`` and enforces its own ``workspace_id`` predicates. Rather than
maintain a second, synchronous data-access path — which would mean
reimplementing that tenant scoping, and getting it wrong — tasks call
``run()`` and reuse the services unchanged.

One event loop and one engine per worker process. asyncpg binds pooled
connections to the loop that opened them, so a fresh loop per task would
throw away the pool on every message.
"""

import asyncio
from collections.abc import AsyncIterator, Coroutine
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from relaydesk.config import get_settings

_loop: asyncio.AbstractEventLoop | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_worker_process() -> None:
    """Called once per worker process, from Celery's ``worker_process_init``."""
    global _loop, _session_factory

    _loop = asyncio.new_event_loop()
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    _session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )


def reset_for_tests() -> None:
    global _loop, _session_factory
    _loop = None
    _session_factory = None


def run[T](coro: Coroutine[Any, Any, T]) -> T:
    if _loop is None:
        coro.close()
        raise RuntimeError(
            "Worker process is not initialised; init_worker_process() must run first."
        )
    return _loop.run_until_complete(coro)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError(
            "Worker process is not initialised; init_worker_process() must run first."
        )
    async with _session_factory() as session:
        yield session
