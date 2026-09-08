import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import AwareDatetime

from relaydesk.api.deps import DbSession
from relaydesk.api.v1.deps import ApiPrincipal, requires
from relaydesk.models import ApiKeyScope, ConversationStatus, Priority
from relaydesk.schemas.v1 import (
    ConversationCreate,
    ConversationOut,
    ConversationPage,
    ConversationUpdate,
    MessageCreate,
    MessageOut,
    MessagePage,
    conversation_out,
    message_out,
)
from relaydesk.services import conversations, tickets

router = APIRouter()

Reader = Annotated[ApiPrincipal, Depends(requires(ApiKeyScope.conversations_read))]
Writer = Annotated[ApiPrincipal, Depends(requires(ApiKeyScope.conversations_write))]


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


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_route(
    payload: ConversationCreate,
    principal: Writer,
    session: DbSession,
    response: Response,
) -> ConversationOut:
    """Open a ticket.

    Answers 201 for a new conversation and 200 when ``external_id`` matched
    one this workspace already has -- so a caller retrying a batch can tell
    what it actually created without the retry costing anything.
    """
    conversation, created = await tickets.create_from_api(
        session,
        principal.workspace_id,
        email=payload.customer_email,
        name=payload.customer_name,
        subject=payload.subject,
        message=payload.message,
        priority=payload.priority,
        external_id=payload.external_id,
        metadata=payload.metadata,
        actor=principal.actor,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return conversation_out(conversation)


@router.get("/{conversation_id}", response_model=ConversationOut)
async def get_route(
    conversation_id: uuid.UUID, principal: Reader, session: DbSession
) -> ConversationOut:
    conversation = await conversations.get_conversation(
        session, principal.workspace_id, conversation_id
    )
    return conversation_out(conversation)


@router.get("/{conversation_id}/messages", response_model=MessagePage)
async def list_messages_route(
    conversation_id: uuid.UUID,
    principal: Reader,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
) -> MessagePage:
    """A conversation's thread, oldest first.

    Paged like ``/v1/conversations`` and ``/v1/contacts``, not returned as a
    bare array: a thread is unbounded and each message carries a full body,
    so a hundred-message ticket would otherwise be one enormous response
    with no way to add paging later without a v2.

    The order is oldest-first -- the reverse of the two other paged lists --
    because that is the order a thread is read in, and callers will depend
    on it.
    """
    rows, next_cursor = await conversations.list_messages(
        session, principal.workspace_id, conversation_id, limit=limit, cursor=cursor
    )
    return MessagePage(data=[message_out(row) for row in rows], next_cursor=next_cursor)


Replier = Annotated[ApiPrincipal, Depends(requires(ApiKeyScope.messages_write))]


@router.patch("/{conversation_id}", response_model=ConversationOut)
async def update_route(
    conversation_id: uuid.UUID,
    payload: ConversationUpdate,
    principal: Writer,
    session: DbSession,
) -> ConversationOut:
    """Change status, priority or assignee.

    Reads the conversation first so an id belonging to another workspace
    answers 404 before any field is considered -- including for an empty
    body, which must not become a way to probe for ids that exist.

    The assignee is applied *before* status and priority, deliberately.
    ``status``/``priority`` arrive as Pydantic-validated enums, so by the
    time this body runs they cannot fail against the database --
    ``set_status``/``set_priority`` can only raise from
    ``get_conversation``, which has already succeeded above.
    ``assignee_id`` is the one field whose validity is a database lookup:
    ``set_assignee`` 404s when the id does not name an active member. Doing
    it first means that the sole realistic failure happens before anything
    else in this request has committed, so a caller never sees a 404 that
    was itself the result of a partial write.
    """
    conversation = await conversations.get_conversation(
        session, principal.workspace_id, conversation_id
    )
    actor = principal.actor
    mutated = False

    # Checked by presence, not by ``is not None``: ``assignee_id`` is
    # ``uuid.UUID | None``, so an explicit ``{"assignee_id": null}`` and an
    # omitted field both parse to ``None``. Only ``model_fields_set``
    # distinguishes "unassign this" from "leave it alone" -- the same
    # reasoning the console's ``patch_conversation`` already applies.
    if "assignee_id" in payload.model_fields_set:
        conversation = await conversations.set_assignee(
            session,
            principal.workspace_id,
            conversation_id,
            payload.assignee_id,
            actor,
        )
        mutated = True
    if payload.status is not None:
        conversation = await conversations.set_status(
            session, principal.workspace_id, conversation_id, payload.status, actor
        )
        mutated = True
    if payload.priority is not None:
        conversation = await conversations.set_priority(
            session, principal.workspace_id, conversation_id, payload.priority, actor
        )
        mutated = True

    if mutated:
        # Each ``set_*`` call above commits, and ``updated_at`` carries
        # ``onupdate=func.now()`` -- a server-computed value that Postgres
        # does not hand back inline, so SQLAlchemy leaves it (and
        # ``assignee_id``) expired on the instance. ``conversation_out``
        # reads both directly, not through a relationship, so touching
        # either without a refresh first raises ``MissingGreenlet``. See
        # the identical note in ``services.tickets.create_from_api``.
        await session.refresh(
            conversation, ["labels", "assignee", "updated_at", "assignee_id"]
        )
    return conversation_out(conversation)


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_message_route(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    principal: Replier,
    session: DbSession,
) -> MessageOut:
    """Send a reply to the customer.

    Requires ``messages:write``, which ``conversations:write`` does not
    imply: this one puts mail in a customer's inbox under the workspace's
    name, and the delivery is queued the moment it returns.

    The response is serialised from the object ``add_reply`` hands back, not
    from a re-read of the thread. Taking the last row of a re-read would key
    off ``sent_at``, which an *inbound* message can carry up to an hour into
    the future (``ingest._MAX_FUTURE_SKEW`` trusts the sender's ``Date:``
    header that far) -- so a customer whose clock runs fast would have
    *their* message returned as the one this caller just created. That is
    also a scope bypass: this route requires only ``messages:write``, which
    does not imply ``conversations:read`` (spec D5), so a reply-only
    integration must never be handed a customer message's body and ids.
    """
    _conversation, message = await conversations.add_reply(
        session,
        principal.workspace_id,
        conversation_id,
        payload.body,
        principal.actor,
    )
    return message_out(message)


Labeller = Annotated[ApiPrincipal, Depends(requires(ApiKeyScope.labels_write))]


@router.put("/{conversation_id}/labels/{label_id}", response_model=ConversationOut)
async def add_label_route(
    conversation_id: uuid.UUID,
    label_id: uuid.UUID,
    principal: Labeller,
    session: DbSession,
) -> ConversationOut:
    conversation = await conversations.add_label(
        session, principal.workspace_id, conversation_id, label_id, principal.actor
    )
    return conversation_out(conversation)


@router.delete("/{conversation_id}/labels/{label_id}", response_model=ConversationOut)
async def remove_label_route(
    conversation_id: uuid.UUID,
    label_id: uuid.UUID,
    principal: Labeller,
    session: DbSession,
) -> ConversationOut:
    conversation = await conversations.remove_label(
        session, principal.workspace_id, conversation_id, label_id, principal.actor
    )
    return conversation_out(conversation)
