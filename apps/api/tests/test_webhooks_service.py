import pytest

from relaydesk.errors import Conflict, Invalid, NotFound
from relaydesk.models import WebhookMethod
from relaydesk.services import webhooks
from tests.factories import make_workspace


async def register(session, workspace, **overrides):
    payload = {
        "name": "refund_order",
        "description": "Refunds an order by its order_id.",
        "method": WebhookMethod.post,
        "url": "https://api.example.com/relaydesk/refund",
        "params": [],
        "created_by_user_id": None,
    }
    payload.update(overrides)
    return await webhooks.create(session, workspace.id, **payload)


async def test_a_new_webhook_gets_its_own_secret(db_session) -> None:
    workspace = await make_workspace(db_session)

    one = await register(db_session, workspace)
    two = await register(db_session, workspace, name="lookup_subscription")

    assert one.secret.startswith("whsec_")
    assert len(one.secret) > 40
    # Per webhook, not per workspace (spec D3): a leak is scoped to one
    # integration.
    assert one.secret != two.secret


@pytest.mark.parametrize(
    "name",
    ["Refund Order", "refund-order", "9lives", "", "   ", "a" * 65, "réfund", "_lead"],
)
async def test_a_name_that_is_not_an_identifier_is_refused(db_session, name) -> None:
    workspace = await make_workspace(db_session)
    with pytest.raises(Invalid):
        await register(db_session, workspace, name=name)


async def test_a_blank_description_is_refused(db_session) -> None:
    """It is the text a tool-selecting caller reads, not decoration."""
    workspace = await make_workspace(db_session)
    with pytest.raises(Invalid):
        await register(db_session, workspace, description="   ")


async def test_a_duplicate_name_in_one_workspace_is_a_conflict(db_session) -> None:
    workspace = await make_workspace(db_session)
    await register(db_session, workspace)

    with pytest.raises(Conflict):
        await register(db_session, workspace)


async def test_the_same_name_in_two_workspaces_is_allowed(db_session) -> None:
    one = await make_workspace(db_session, slug="chronon")
    two = await make_workspace(db_session, slug="northwind")

    await register(db_session, one)
    await register(db_session, two)  # no conflict across the tenant boundary


async def test_a_url_that_is_not_https_is_refused_at_registration(db_session) -> None:
    workspace = await make_workspace(db_session)
    with pytest.raises(Invalid):
        await register(db_session, workspace, url="http://api.example.com/refund")


async def test_another_workspaces_webhook_is_not_found(db_session) -> None:
    mine = await make_workspace(db_session, slug="chronon")
    theirs = await make_workspace(db_session, slug="northwind")
    hook = await register(db_session, mine)

    with pytest.raises(NotFound):
        await webhooks.get(db_session, theirs.id, hook.id)
    with pytest.raises(NotFound):
        await webhooks.rotate_secret(db_session, theirs.id, hook.id)
    with pytest.raises(NotFound):
        await webhooks.update(db_session, theirs.id, hook.id, name="stolen")
    with pytest.raises(NotFound):
        await webhooks.delete(db_session, theirs.id, hook.id)


async def test_the_list_is_scoped_to_its_workspace(db_session) -> None:
    mine = await make_workspace(db_session, slug="chronon")
    theirs = await make_workspace(db_session, slug="northwind")
    await register(db_session, mine)

    assert len(await webhooks.list_webhooks(db_session, mine.id)) == 1
    assert await webhooks.list_webhooks(db_session, theirs.id) == []


async def test_rotation_replaces_the_secret_and_keeps_everything_else(
    db_session,
) -> None:
    workspace = await make_workspace(db_session)
    hook = await register(db_session, workspace)
    before = hook.secret

    rotated = await webhooks.rotate_secret(db_session, workspace.id, hook.id)

    assert rotated.secret != before
    assert rotated.secret.startswith("whsec_")
    assert rotated.name == "refund_order"
    assert rotated.url == "https://api.example.com/relaydesk/refund"


async def test_update_changes_only_what_was_supplied(db_session) -> None:
    workspace = await make_workspace(db_session)
    hook = await register(db_session, workspace)

    updated = await webhooks.update(
        db_session, workspace.id, hook.id, description="Refunds, partially."
    )

    assert updated.description == "Refunds, partially."
    assert updated.name == "refund_order"
    assert updated.method is WebhookMethod.post


async def test_update_can_clear_the_parameter_list(db_session) -> None:
    """An empty list clears; ``None`` means untouched."""
    workspace = await make_workspace(db_session)
    hook = await register(
        db_session,
        workspace,
        params=[
            {"name": "order_id", "type": "string", "description": "", "required": True}
        ],
    )

    updated = await webhooks.update(db_session, workspace.id, hook.id, params=[])

    assert updated.params == []


async def test_update_refuses_a_name_taken_by_a_sibling(db_session) -> None:
    workspace = await make_workspace(db_session)
    await register(db_session, workspace)
    other = await register(db_session, workspace, name="lookup_subscription")

    with pytest.raises(Conflict):
        await webhooks.update(db_session, workspace.id, other.id, name="refund_order")


async def test_a_deleted_webhook_is_gone(db_session) -> None:
    workspace = await make_workspace(db_session)
    hook = await register(db_session, workspace)

    await webhooks.delete(db_session, workspace.id, hook.id)

    with pytest.raises(NotFound):
        await webhooks.get(db_session, workspace.id, hook.id)
