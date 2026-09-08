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


@router.post(
    "",
    response_model=ConversationOut,
    status_code=status.HTTP_201_CREATED,
    # Declared, not just returned. ``status_code=201`` alone is all the
    # OpenAPI document would say, so a generated SDK would treat the
    # idempotent replay -- which spec section 6 makes first-class, and which
    # is the whole reason an interrupted import is safe to re-run -- as an
    # unexpected response.
    responses={
        200: {
            "model": ConversationOut,
            "description": (
                "``external_id`` matched a conversation this workspace "
                "already has; it is returned unchanged and nothing was "
                "created."
            ),
        }
    },
)
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

    What that buys is precisely "no partial commit precedes an assignee
    404", and **not** "PATCH is atomic". Each ``set_*`` commits on its own,
    so an infrastructure failure -- a dropped connection, a deadlock, a
    timeout -- during the second or third commit can still leave an earlier
    field committed while the caller sees a 500. That is true of every
    multi-call service sequence in this codebase and is not something to fix
    here; it is written down so a future reader does not over-read the
    paragraph above.
    """
    conversation = await conversations.get_conversation(
        session, principal.workspace_id, conversation_id
    )
    actor = principal.actor

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
    if payload.status is not None:
        conversation = await conversations.set_status(
            session, principal.workspace_id, conversation_id, payload.status, actor
        )
    if payload.priority is not None:
        conversation = await conversations.set_priority(
            session, principal.workspace_id, conversation_id, payload.priority, actor
        )

    # No refresh here. Every ``set_*`` above refreshes ``updated_at`` and
    # ``assignee_id`` itself after its own commit, which is where that
    # belongs: ``Conversation.updated_at`` carries ``onupdate=func.now()``,
    # so any UPDATE expires it, and a route is the wrong place to have to
    # know that. This used to be patched here and in
    # ``tickets.create_from_api`` -- two call sites that happened to have
    # been bitten -- while ``set_status`` and ``set_priority`` had no refresh
    # at all and would have crashed the next caller to serialise their
    # result.
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
