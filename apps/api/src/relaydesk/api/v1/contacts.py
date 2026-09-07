import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from relaydesk.api.deps import DbSession
from relaydesk.api.v1.deps import ApiPrincipal, requires
from relaydesk.models import ApiKeyScope
from relaydesk.schemas.v1 import ContactOut, ContactPage, contact_out
from relaydesk.services import contacts

router = APIRouter()

Reader = Annotated[ApiPrincipal, Depends(requires(ApiKeyScope.contacts_read))]


@router.get("", response_model=ContactPage)
async def list_route(
    principal: Reader,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
) -> ContactPage:
    rows, next_cursor = await contacts.list_contacts(
        session, principal.workspace_id, limit=limit, cursor=cursor
    )
    return ContactPage(
        data=[contact_out(row) for row in rows], next_cursor=next_cursor
    )


@router.get("/{contact_id}", response_model=ContactOut)
async def get_route(
    contact_id: uuid.UUID, principal: Reader, session: DbSession
) -> ContactOut:
    contact = await contacts.get_contact(session, principal.workspace_id, contact_id)
    return contact_out(contact)
