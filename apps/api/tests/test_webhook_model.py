import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from relaydesk.models import Webhook, WebhookMethod
from tests.factories import make_workspace


def build(workspace_id, name: str = "refund_order") -> Webhook:
    return Webhook(
        workspace_id=workspace_id,
        name=name,
        description="Refunds an order by its order_id.",
        method=WebhookMethod.post,
        url="https://api.example.com/relaydesk/refund",
        params=[
            {
                "name": "order_id",
                "type": "string",
                "description": "The order to refund.",
                "required": True,
            }
        ],
        secret="whsec_placeholder",
    )


async def test_params_round_trip_through_jsonb(db_session) -> None:
    workspace = await make_workspace(db_session)
    hook = build(workspace.id)
    db_session.add(hook)
    await db_session.commit()
    await db_session.refresh(hook)

    assert hook.params[0]["name"] == "order_id"
    # Booleans survive as booleans, not as the strings a text column would
    # have made of them.
    assert hook.params[0]["required"] is True


async def test_the_method_is_stored_as_the_http_verb(db_session) -> None:
    workspace = await make_workspace(db_session)
    hook = build(workspace.id)
    db_session.add(hook)
    await db_session.commit()
    await db_session.refresh(hook)

    assert hook.method is WebhookMethod.post
    assert hook.method.value == "POST"


async def test_two_webhooks_in_one_workspace_cannot_share_a_name(db_session) -> None:
    workspace = await make_workspace(db_session)
    db_session.add(build(workspace.id))
    await db_session.commit()

    db_session.add(build(workspace.id))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_two_workspaces_may_each_hold_the_same_name(db_session) -> None:
    one = await make_workspace(db_session, slug="chronon")
    two = await make_workspace(db_session, slug="northwind")

    db_session.add(build(one.id))
    db_session.add(build(two.id))
    await db_session.commit()  # the constraint stops at the tenant boundary


async def test_a_method_outside_the_closed_set_is_refused(db_session) -> None:
    """The CHECK constraint the migration writes, not the Python enum.

    Inserted as raw SQL on purpose: going through the ORM would be stopped by
    SQLAlchemy's own enum validation and would prove nothing about the
    database, which is what has to hold the line for anything writing outside
    this process.
    """
    workspace = await make_workspace(db_session)
    await db_session.commit()

    with pytest.raises(IntegrityError):
        await db_session.execute(
            sa.text(
                "INSERT INTO webhooks "
                "(id, workspace_id, name, description, method, url, secret) "
                "VALUES (gen_random_uuid(), :ws, 'trace_it', 'x', 'TRACE', "
                "'https://api.example.com/x', 'whsec_x')"
            ),
            {"ws": workspace.id},
        )
