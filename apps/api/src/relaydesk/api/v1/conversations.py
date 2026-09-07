import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime

from relaydesk.api.deps import DbSession
from relaydesk.api.v1.deps import ApiPrincipal, requires
from relaydesk.models import ApiKeyScope, ConversationStatus, Priority
from relaydesk.schemas.v1 import (
    ConversationOut,
    ConversationPage,
    MessageOut,
    conversation_out,
    message_out,
)
from relaydesk.services import conversations

router = APIRouter()

Reader = Annotated[ApiPrincipal, Depends(requires(ApiKeyScope.conversations_read))]


@router.get("", response_model=ConversationPage)
async def list_route(
    principal: Reader,
    session: DbSession,
    status: ConversationStatus | None = None,
    priority: Priority | None = None,
    assignee_id: uuid.UUID | None = None,
    label_id: uuid.UUID | None = None,
    # Aware, not ``datetime | None``: a naive value would still parse, and
    # asyncpg would then encode it by assuming the *server's* local
    # timezone rather than UTC -- a silently wrong boundary for a sync
    # cursor, which is exactly the bug this parameter exists to prevent.
    # Refusing naive input with a 422 is safer than guessing at it.
    updated_since: AwareDatetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
) -> ConversationPage:
    rows, next_cursor = await conversations.list_conversations(
        session,
        principal.workspace_id,
        status=status,
        priority=priority,
        label_id=label_id,
        assignee_id=assignee_id,
        updated_since=updated_since,
        limit=limit,
        cursor=cursor,
    )
    return ConversationPage(
        data=[conversation_out(row) for row in rows], next_cursor=next_cursor
    )


@router.get("/{conversation_id}", response_model=ConversationOut)
async def get_route(
    conversation_id: uuid.UUID, principal: Reader, session: DbSession
) -> ConversationOut:
    conversation = await conversations.get_conversation(
        session, principal.workspace_id, conversation_id
    )
    return conversation_out(conversation)


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
async def list_messages_route(
    conversation_id: uuid.UUID, principal: Reader, session: DbSession
) -> list[MessageOut]:
    rows = await conversations.list_messages(
        session, principal.workspace_id, conversation_id
    )
    return [message_out(row) for row in rows]
