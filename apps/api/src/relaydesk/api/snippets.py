import uuid

from fastapi import APIRouter, Response, status

from relaydesk.api.deps import DbSession, Scope
from relaydesk.models import Snippet
from relaydesk.schemas.snippet import SnippetCreateRequest, SnippetOut, SnippetPatch
from relaydesk.services import snippets

router = APIRouter()


def _out(snippet: Snippet) -> SnippetOut:
    return SnippetOut(
        id=str(snippet.id), title=snippet.title, content=snippet.content
    )


@router.get("", response_model=list[SnippetOut])
async def list_route(scope: Scope, session: DbSession) -> list[SnippetOut]:
    """Readable by every member, unlike the writes below.

    The console gates Settings -> Templates on `requireAdmin`, but the
    snippets themselves are what the reply composer's `/` menu is made of,
    and that belongs to whoever is answering the ticket.
    """
    rows = await snippets.list_for(session, scope.workspace_id)
    return [_out(snippet) for snippet in rows]


@router.post("", response_model=SnippetOut, status_code=status.HTTP_201_CREATED)
async def create_route(
    payload: SnippetCreateRequest, scope: Scope, session: DbSession
) -> SnippetOut:
    scope.require_admin()
    snippet = await snippets.create(
        session, scope.workspace_id, payload.title, payload.content
    )
    await session.commit()
    return _out(snippet)


@router.patch("/{snippet_id}", response_model=SnippetOut)
async def update_route(
    snippet_id: uuid.UUID,
    payload: SnippetPatch,
    scope: Scope,
    session: DbSession,
) -> SnippetOut:
    scope.require_admin()
    snippet = await snippets.update(
        session,
        scope.workspace_id,
        snippet_id,
        title=payload.title,
        content=payload.content,
    )
    await session.commit()
    return _out(snippet)


@router.delete("/{snippet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_route(
    snippet_id: uuid.UUID, scope: Scope, session: DbSession
) -> Response:
    scope.require_admin()
    await snippets.delete(session, scope.workspace_id, snippet_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
