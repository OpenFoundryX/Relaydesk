import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from relaydesk.api.deps import DbSession, Scope
from relaydesk.errors import Invalid
from relaydesk.models import ConversationStatus, Priority
from relaydesk.schemas.conversation import (
    ActivityEventOut,
    BulkStatusRequest,
    ConversationOut,
    ConversationPage,
    ConversationPatch,
    CountsResponse,
    DraftOut,
    MessageOut,
    ReplyRequest,
    StatusCountOut,
    activity_out,
    conversation_out,
    message_out,
)
from relaydesk.services import conversations, views

router = APIRouter()


def _parsed_status(raw: str) -> ConversationStatus:
    try:
        return ConversationStatus(raw)
    except ValueError:
        raise Invalid(f"Unknown status {raw!r}.") from None


def _parsed_priority(raw: str) -> Priority:
    try:
        return Priority(raw)
    except ValueError:
        raise Invalid(f"Unknown priority {raw!r}.") from None


@router.get("", response_model=ConversationPage)
async def list_route(
    scope: Scope,
    session: DbSession,
    status: str | None = None,
    label_id: Annotated[uuid.UUID | None, Query(alias="labelId")] = None,
    assignee_id: Annotated[uuid.UUID | None, Query(alias="assigneeId")] = None,
    view_id: Annotated[uuid.UUID | None, Query(alias="viewId")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
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

    view = None
    if view_id is not None:
        # Raises NotFound for a foreign id, so an unowned viewId 404s
        # instead of silently returning an unfiltered list.
        view = await views.get_view(session, scope.workspace_id, view_id)

    rows, next_cursor = await conversations.list_conversations(
        session,
        scope.workspace_id,
        status=real_status,
        label_id=label_id,
        assignee_id=assignee_id,
        has_draft=has_draft,
        view=view,
        viewer=scope.user,
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


@router.post("/bulk-status", status_code=status.HTTP_204_NO_CONTENT)
async def bulk_status_route(
    payload: BulkStatusRequest, scope: Scope, session: DbSession
) -> None:
    new_status = _parsed_status(payload.status)
    await conversations.bulk_set_status(
        session, scope.workspace_id, payload.ids, new_status, scope.user
    )


@router.get("/{conversation_id}", response_model=ConversationOut)
async def get_route(
    conversation_id: uuid.UUID, scope: Scope, session: DbSession
) -> ConversationOut:
    conversation = await conversations.get_conversation(
        session, scope.workspace_id, conversation_id
    )
    return conversation_out(conversation, scope.workspace.timezone)


@router.patch("/{conversation_id}", response_model=ConversationOut)
async def patch_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationPatch,
    scope: Scope,
    session: DbSession,
) -> ConversationOut:
    # Parse every field up front so a bad value in one (e.g. an unknown
    # priority) 422s before an earlier field (e.g. status) has been
    # committed.
    new_status = _parsed_status(payload.status) if payload.status is not None else None
    new_priority = (
        _parsed_priority(payload.priority) if payload.priority is not None else None
    )

    conversation = None
    if new_status is not None:
        conversation = await conversations.set_status(
            session, scope.workspace_id, conversation_id, new_status, scope.user
        )
    if new_priority is not None:
        conversation = await conversations.set_priority(
            session, scope.workspace_id, conversation_id, new_priority, scope.user
        )
    if "assignee_id" in payload.model_fields_set:
        conversation = await conversations.set_assignee(
            session,
            scope.workspace_id,
            conversation_id,
            payload.assignee_id,
            scope.user,
        )
    if conversation is None:
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


@router.post(
    "/{conversation_id}/replies",
    response_model=ConversationOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_reply_route(
    conversation_id: uuid.UUID, payload: ReplyRequest, scope: Scope, session: DbSession
) -> ConversationOut:
    conversation = await conversations.add_reply(
        session, scope.workspace_id, conversation_id, payload.body, scope.user
    )
    if payload.resolve:
        conversation = await conversations.set_status(
            session,
            scope.workspace_id,
            conversation_id,
            ConversationStatus.resolved,
            scope.user,
        )
    return conversation_out(conversation, scope.workspace.timezone)


@router.delete("/{conversation_id}/draft", status_code=status.HTTP_204_NO_CONTENT)
async def discard_draft_route(
    conversation_id: uuid.UUID, scope: Scope, session: DbSession
) -> None:
    await conversations.discard_draft(session, scope.workspace_id, conversation_id)


@router.put("/{conversation_id}/labels/{label_id}", response_model=ConversationOut)
async def add_label_route(
    conversation_id: uuid.UUID, label_id: uuid.UUID, scope: Scope, session: DbSession
) -> ConversationOut:
    conversation = await conversations.add_label(
        session, scope.workspace_id, conversation_id, label_id, scope.user
    )
    return conversation_out(conversation, scope.workspace.timezone)


@router.delete("/{conversation_id}/labels/{label_id}", response_model=ConversationOut)
async def remove_label_route(
    conversation_id: uuid.UUID, label_id: uuid.UUID, scope: Scope, session: DbSession
) -> ConversationOut:
    conversation = await conversations.remove_label(
        session, scope.workspace_id, conversation_id, label_id, scope.user
    )
    return conversation_out(conversation, scope.workspace.timezone)
