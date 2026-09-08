import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Conflict, Invalid, NotFound
from relaydesk.models import Snippet


async def list_for(session: AsyncSession, workspace_id: uuid.UUID) -> list[Snippet]:
    """Every snippet in the workspace, in the order the `/` menu shows them.

    Title order, not recency: the menu is something an agent learns the
    shape of, and a list that reorders itself as snippets are edited would
    move the entry they were reaching for.
    """
    return list(
        await session.scalars(
            sa.select(Snippet)
            .where(Snippet.workspace_id == workspace_id)
            .order_by(Snippet.title)
        )
    )


def _clean(title: str, content: str) -> tuple[str, str]:
    trimmed_title = title.strip()
    if not trimmed_title:
        raise Invalid("A snippet needs a title.")
    if not content.strip():
        raise Invalid("A snippet needs some content.")
    # The title is trimmed because it is an identifier in the `/` menu; the
    # content is not, because it is inserted into a reply verbatim and its
    # leading or trailing blank line may be deliberate.
    return trimmed_title, content


async def _titled(
    session: AsyncSession, workspace_id: uuid.UUID, title: str
) -> Snippet | None:
    # `title` is CITEXT, so this comparison is case-insensitive at the
    # database level -- no `func.lower()`, and matching the unique
    # constraint that backs it up.
    return await session.scalar(
        sa.select(Snippet).where(
            Snippet.workspace_id == workspace_id, Snippet.title == title
        )
    )


async def create(
    session: AsyncSession, workspace_id: uuid.UUID, title: str, content: str
) -> Snippet:
    trimmed_title, content = _clean(title, content)
    if await _titled(session, workspace_id, trimmed_title) is not None:
        raise Conflict("A snippet with that title already exists.")

    snippet = Snippet(
        workspace_id=workspace_id, title=trimmed_title, content=content
    )
    session.add(snippet)
    await session.flush()
    return snippet


async def _get(
    session: AsyncSession, workspace_id: uuid.UUID, snippet_id: uuid.UUID
) -> Snippet:
    snippet = await session.scalar(
        sa.select(Snippet).where(
            Snippet.id == snippet_id, Snippet.workspace_id == workspace_id
        )
    )
    if snippet is None:
        raise NotFound("That snippet does not exist.")
    return snippet


async def update(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    snippet_id: uuid.UUID,
    *,
    title: str | None = None,
    content: str | None = None,
) -> Snippet:
    snippet = await _get(session, workspace_id, snippet_id)
    trimmed_title, cleaned_content = _clean(
        snippet.title if title is None else title,
        snippet.content if content is None else content,
    )

    if title is not None:
        existing = await _titled(session, workspace_id, trimmed_title)
        # The edit dialog submits every field, so an edit that only changed
        # the content still sends the unchanged title back. That is a hit on
        # the row being edited, not a collision with another one.
        if existing is not None and existing.id != snippet.id:
            raise Conflict("A snippet with that title already exists.")
        snippet.title = trimmed_title
    if content is not None:
        snippet.content = cleaned_content

    await session.flush()
    return snippet


async def delete(
    session: AsyncSession, workspace_id: uuid.UUID, snippet_id: uuid.UUID
) -> None:
    snippet = await _get(session, workspace_id, snippet_id)
    await session.delete(snippet)
    await session.flush()
