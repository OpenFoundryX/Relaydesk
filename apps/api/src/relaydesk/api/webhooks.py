"""Console routes for the webhook registry.

Admin-only throughout: a webhook is a credential shared with a third party
and an endpoint the server will make requests to, and neither is something an
agent should be able to add while triaging a ticket.
"""

import uuid
from datetime import timedelta

from fastapi import APIRouter, status

from relaydesk.api.deps import DbSession, Scope
from relaydesk.config import get_settings
from relaydesk.errors import TooManyRequests
from relaydesk.models import Webhook
from relaydesk.schemas.webhook import (
    WebhookCreate,
    WebhookCreated,
    WebhookOut,
    WebhookTestRequest,
    WebhookTestResult,
    WebhookUpdate,
)
from relaydesk.services import ratelimit, webhook_dispatch, webhooks

router = APIRouter()

TEST_BUCKET = "webhook_test"


def _out(webhook: Webhook) -> WebhookOut:
    return WebhookOut(
        id=str(webhook.id),
        name=webhook.name,
        description=webhook.description,
        method=webhook.method,
        url=webhook.url,
        params=webhook.params,
        created_at=webhook.created_at,
    )


@router.get("", response_model=list[WebhookOut])
async def list_route(scope: Scope, session: DbSession) -> list[WebhookOut]:
    scope.require_admin()
    rows = await webhooks.list_webhooks(session, scope.workspace_id)
    return [_out(row) for row in rows]


@router.post("", response_model=WebhookCreated, status_code=status.HTTP_201_CREATED)
async def create_route(
    payload: WebhookCreate, scope: Scope, session: DbSession
) -> WebhookCreated:
    scope.require_admin()
    webhook = await webhooks.create(
        session,
        scope.workspace_id,
        name=payload.name,
        description=payload.description,
        method=payload.method,
        url=payload.url,
        params=[param.model_dump() for param in payload.params],
        created_by_user_id=scope.user.id,
    )
    return WebhookCreated(webhook=_out(webhook), secret=webhook.secret)


@router.patch("/{webhook_id}", response_model=WebhookOut)
async def update_route(
    webhook_id: uuid.UUID, payload: WebhookUpdate, scope: Scope, session: DbSession
) -> WebhookOut:
    scope.require_admin()
    webhook = await webhooks.update(
        session,
        scope.workspace_id,
        webhook_id,
        name=payload.name,
        description=payload.description,
        method=payload.method,
        url=payload.url,
        params=(
            None
            if payload.params is None
            else [param.model_dump() for param in payload.params]
        ),
    )
    return _out(webhook)


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_route(
    webhook_id: uuid.UUID, scope: Scope, session: DbSession
) -> None:
    scope.require_admin()
    await webhooks.delete(session, scope.workspace_id, webhook_id)


@router.post("/{webhook_id}/secret", response_model=WebhookCreated)
async def rotate_route(
    webhook_id: uuid.UUID, scope: Scope, session: DbSession
) -> WebhookCreated:
    """Mint a new signing secret for an existing webhook.

    Rotation rather than delete-and-recreate: the URL, the description and
    the parameters are what a receiver was written against, and only the key
    needs to change when it leaks.
    """
    scope.require_admin()
    webhook = await webhooks.rotate_secret(session, scope.workspace_id, webhook_id)
    return WebhookCreated(webhook=_out(webhook), secret=webhook.secret)


@router.post("/{webhook_id}/test", response_model=WebhookTestResult)
async def test_route(
    webhook_id: uuid.UUID,
    payload: WebhookTestRequest,
    scope: Scope,
    session: DbSession,
) -> WebhookTestResult:
    """Call the webhook once and report what came back.

    The status is about *this* request, not the receiver's: a receiver that
    answers 500 is a successful test that found a broken endpoint, so it is a
    200 carrying ``ok: false``. Only a caller error -- a missing or
    uncoercible argument -- is a 4xx, because then no call was made at all.
    """
    scope.require_admin()
    settings = get_settings()

    # Charged before the call, and deliberately first: ``ratelimit.check``
    # commits, so anything pending would commit with it. Nothing is pending
    # here -- this route reads a row and makes an HTTP request -- and paying
    # up front is what stops a refused dispatch from also refunding the
    # attempt. An endpoint that makes the server issue an outbound request to
    # a workspace-supplied URL is a request proxy; admin-only is not the same
    # as unmetered (spec D9).
    within = await ratelimit.check(
        session,
        TEST_BUCKET,
        str(scope.workspace_id),
        limit=settings.webhook_test_hourly_cap,
        window=timedelta(hours=1),
    )
    if not within:
        raise TooManyRequests(
            "Too many test requests. Try again later.",
            headers={"Retry-After": "3600"},
        )

    webhook = await webhooks.get(session, scope.workspace_id, webhook_id)
    result = await webhook_dispatch.dispatch(webhook, payload.arguments)
    return WebhookTestResult(
        ok=result.ok,
        status=result.status,
        duration_ms=result.duration_ms,
        response_body=result.response_body,
        error=result.error,
    )
