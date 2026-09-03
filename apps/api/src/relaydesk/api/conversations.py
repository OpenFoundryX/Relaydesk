import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from relaydesk.api.deps import DbSession, Scope
from relaydesk.errors import Invalid
from relaydesk.models import ConversationStatus
from relaydesk.schemas.conversation import (
    ActivityEventOut,
    ConversationOut,
    ConversationPage,
    CountsResponse,
    DraftOut,
    MessageOut,
    StatusCountOut,
    activity_out,
    conversation_out,
    message_out,
)
from relaydesk.services import conversations

router = APIRouter()


@router.get("", response_model=ConversationPage)
async def list_route(
    scope: Scope,
    session: DbSession,
    status: str | None = None,
    label_id: Annotated[uuid.UUID | None, Query(alias="labelId")] = None,
    assignee_id: Annotated[uuid.UUID | None, Query(alias="assigneeId")] = None,
    view_id: Annotated[uuid.UUID | None, Query(alias="viewId")] = None,
    limit: int = 50,
    cursor: str | None = None,
) -> ConversationPage:
    # "all" and "drafts" are sidebar filters, not stored statuses.
    real_status = None
    has_draft = None
    if status == "drafts":
        has_draft = True
    elif status and status != "all":
        try:
            real_status = ConversationStatus(status)
        except ValueError:
            raise Invalid(f"Unknown status {status!r}.") from None

    rows, next_cursor = await conversations.list_conversations(
        session,
        scope.workspace_id,
        status=real_status,
        label_id=label_id,
        assignee_id=assignee_id,
        has_draft=has_draft,
        limit=limit,
        cursor=cursor,
    )
    return ConversationPage(
        items=[conversation_out(row, scope.workspace.timezone) for row in rows],
        next_cursor=next_cursor,
    )


@router.get("/counts", response_model=CountsResponse)
async def counts_route(scope: Scope, session: DbSession) -> CountsResponse:
    counts = await conversations.status_counts(session, scope.workspace_id)
    drafts = await conversations.draft_count(session, scope.workspace_id)
    return CountsResponse(
        statuses=[
            StatusCountOut(status=status.value, count=count)
            for status, count in counts.items()
        ],
        drafts=drafts,
    )


@router.get("/{conversation_id}", response_model=ConversationOut)
async def get_route(
    conversation_id: uuid.UUID, scope: Scope, session: DbSession
) -> ConversationOut:
    conversation = await conversations.get_conversation(
        session, scope.workspace_id, conversation_id
    )
    return conversation_out(conversation, scope.workspace.timezone)


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
async def list_messages_route(
    conversation_id: uuid.UUID, scope: Scope, session: DbSession
) -> list[MessageOut]:
    messages = await conversations.list_messages(
        session, scope.workspace_id, conversation_id
    )
    return [message_out(message, scope.workspace.timezone) for message in messages]


@router.get("/{conversation_id}/draft", response_model=DraftOut)
async def get_draft_route(
    conversation_id: uuid.UUID, scope: Scope, session: DbSession
) -> DraftOut:
    draft = await conversations.get_draft(session, scope.workspace_id, conversation_id)
    return DraftOut(body=draft.body)


@router.get("/{conversation_id}/activity", response_model=list[ActivityEventOut])
async def list_activity_route(
    conversation_id: uuid.UUID, scope: Scope, session: DbSession
) -> list[ActivityEventOut]:
    events = await conversations.list_activity(
        session, scope.workspace_id, conversation_id
    )
    return [activity_out(event, scope.workspace.timezone) for event in events]
