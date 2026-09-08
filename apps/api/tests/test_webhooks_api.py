import pytest

from relaydesk.config import get_settings
from relaydesk.models import Role
from relaydesk.services import webhook_dispatch, webhooks
from tests.factories import make_member, make_workspace, sign_in

# Captured before the autouse fixture below replaces it, for the one test that
# wants the real argument checking. That check runs before any request is
# built, so restoring it still reaches no network.
REAL_DISPATCH = webhook_dispatch.dispatch

PAYLOAD = {
    "name": "refund_order",
    "description": "Refunds an order by its order_id.",
    "method": "POST",
    "url": "https://api.example.com/relaydesk/refund",
    "params": [
        {
            "name": "order_id",
            "type": "string",
            "description": "The order to refund.",
            "required": True,
        }
    ],
}


async def admin_headers(client, db_session, workspace, email="admin@relaydesk.dev"):
    await make_member(db_session, workspace, email=email)
    await db_session.commit()
    return await sign_in(client, db_session, email)


async def agent_headers(client, db_session, workspace):
    await make_member(
        db_session, workspace, email="agent@relaydesk.dev", role=Role.agent
    )
    await db_session.commit()
    return await sign_in(client, db_session, "agent@relaydesk.dev")


async def register(db_session, workspace, name="refund_order"):
    return await webhooks.create(
        db_session,
        workspace.id,
        name=name,
        description="Refunds an order by its order_id.",
        method="POST",
        url="https://api.example.com/relaydesk/refund",
        params=[
            {"name": "order_id", "type": "string", "description": "", "required": True}
        ],
        created_by_user_id=None,
    )


@pytest.fixture(autouse=True)
def never_dispatch(monkeypatch):
    """No test in this module may reach the network.

    Each test that cares about the outcome replaces this with its own.
    """

    async def refuse(webhook, arguments, client=None):
        return webhook_dispatch.DispatchResult(
            ok=True, status=200, duration_ms=1, response_body="ok", error=None
        )

    monkeypatch.setattr(webhook_dispatch, "dispatch", refuse)


async def test_an_admin_registers_a_webhook_and_sees_the_secret(
    client, db_session
) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)

    created = await client.post("/api/webhooks", json=PAYLOAD, headers=headers)

    assert created.status_code == 201, created.text
    body = created.json()
    assert body["secret"].startswith("whsec_")
    assert body["webhook"]["name"] == "refund_order"
    assert body["webhook"]["method"] == "POST"
    assert body["webhook"]["params"][0]["required"] is True
    # camelCase on the wire, matching the console's types.
    assert "createdAt" in body["webhook"]


async def test_the_secret_is_not_offered_in_the_list(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)
    created = await client.post("/api/webhooks", json=PAYLOAD, headers=headers)
    secret = created.json()["secret"]

    listed = await client.get("/api/webhooks", headers=headers)

    assert listed.status_code == 200
    assert [item["name"] for item in listed.json()] == ["refund_order"]
    assert secret not in listed.text


async def test_an_agent_may_not_touch_webhooks(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    hook = await register(db_session, workspace)
    headers = await agent_headers(client, db_session, workspace)

    calls = [
        client.get("/api/webhooks", headers=headers),
        client.post("/api/webhooks", json=PAYLOAD, headers=headers),
        client.patch(
            f"/api/webhooks/{hook.id}", json={"description": "x"}, headers=headers
        ),
        client.delete(f"/api/webhooks/{hook.id}", headers=headers),
        client.post(f"/api/webhooks/{hook.id}/secret", headers=headers),
        client.post(
            f"/api/webhooks/{hook.id}/test", json={"arguments": {}}, headers=headers
        ),
    ]
    for call in calls:
        response = await call
        assert response.status_code == 403, response.text


async def test_another_workspaces_webhook_is_404_not_403(client, db_session) -> None:
    mine = await make_workspace(db_session, slug="chronon")
    theirs = await make_workspace(db_session, slug="northwind")
    hook = await register(db_session, theirs)
    headers = await admin_headers(client, db_session, mine)

    patched = await client.patch(
        f"/api/webhooks/{hook.id}", json={"description": "x"}, headers=headers
    )
    deleted = await client.delete(f"/api/webhooks/{hook.id}", headers=headers)
    rotated = await client.post(f"/api/webhooks/{hook.id}/secret", headers=headers)
    tested = await client.post(
        f"/api/webhooks/{hook.id}/test", json={"arguments": {}}, headers=headers
    )

    assert [patched.status_code, deleted.status_code, rotated.status_code] == [
        404,
        404,
        404,
    ]
    assert tested.status_code == 404


async def test_a_name_that_is_not_an_identifier_is_refused(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)

    response = await client.post(
        "/api/webhooks", json={**PAYLOAD, "name": "Refund Order"}, headers=headers
    )

    assert response.status_code == 422, response.text


async def test_a_url_that_is_not_https_is_refused(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)

    response = await client.post(
        "/api/webhooks",
        json={**PAYLOAD, "url": "http://api.example.com/refund"},
        headers=headers,
    )

    assert response.status_code == 422, response.text


async def test_a_parameter_type_outside_the_closed_set_is_refused(
    client, db_session
) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)

    response = await client.post(
        "/api/webhooks",
        json={
            **PAYLOAD,
            "params": [
                {"name": "x", "type": "object", "description": "", "required": False}
            ],
        },
        headers=headers,
    )

    assert response.status_code == 422, response.text


async def test_a_duplicate_name_is_a_conflict(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)
    await client.post("/api/webhooks", json=PAYLOAD, headers=headers)

    again = await client.post("/api/webhooks", json=PAYLOAD, headers=headers)

    assert again.status_code == 409, again.text


async def test_rotation_returns_a_new_secret(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)
    created = await client.post("/api/webhooks", json=PAYLOAD, headers=headers)
    before = created.json()["secret"]
    webhook_id = created.json()["webhook"]["id"]

    rotated = await client.post(f"/api/webhooks/{webhook_id}/secret", headers=headers)

    assert rotated.status_code == 200, rotated.text
    assert rotated.json()["secret"] != before


async def test_a_patch_changes_only_what_it_names(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)
    created = await client.post("/api/webhooks", json=PAYLOAD, headers=headers)
    webhook_id = created.json()["webhook"]["id"]

    patched = await client.patch(
        f"/api/webhooks/{webhook_id}", json={"method": "GET"}, headers=headers
    )

    assert patched.status_code == 200, patched.text
    assert patched.json()["method"] == "GET"
    assert patched.json()["name"] == "refund_order"


async def test_a_deleted_webhook_leaves_the_list(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)
    created = await client.post("/api/webhooks", json=PAYLOAD, headers=headers)
    webhook_id = created.json()["webhook"]["id"]

    deleted = await client.delete(f"/api/webhooks/{webhook_id}", headers=headers)
    listed = await client.get("/api/webhooks", headers=headers)

    assert deleted.status_code == 204
    assert listed.json() == []


async def test_a_receivers_failure_is_reported_as_a_successful_test(
    client, db_session, monkeypatch
) -> None:
    """The request we were asked to make was made. Its outcome is the body."""
    workspace = await make_workspace(db_session)
    hook = await register(db_session, workspace)
    headers = await admin_headers(client, db_session, workspace)

    async def failing(webhook, arguments, client=None):
        return webhook_dispatch.DispatchResult(
            ok=False, status=500, duration_ms=12, response_body="boom", error=None
        )

    monkeypatch.setattr(webhook_dispatch, "dispatch", failing)

    response = await client.post(
        f"/api/webhooks/{hook.id}/test",
        json={"arguments": {"order_id": "A1"}},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "ok": False,
        "status": 500,
        "durationMs": 12,
        "responseBody": "boom",
        "error": None,
    }


async def test_a_missing_required_argument_is_a_422(
    client, db_session, monkeypatch
) -> None:
    """A caller error, not a failed call -- nothing was sent."""
    workspace = await make_workspace(db_session)
    hook = await register(db_session, workspace)
    headers = await admin_headers(client, db_session, workspace)
    monkeypatch.setattr(webhook_dispatch, "dispatch", REAL_DISPATCH)

    response = await client.post(
        f"/api/webhooks/{hook.id}/test", json={"arguments": {}}, headers=headers
    )

    assert response.status_code == 422, response.text


async def test_the_test_route_is_rate_limited(
    client, db_session, monkeypatch
) -> None:
    workspace = await make_workspace(db_session)
    hook = await register(db_session, workspace)
    headers = await admin_headers(client, db_session, workspace)
    monkeypatch.setattr(get_settings(), "webhook_test_hourly_cap", 1)

    first = await client.post(
        f"/api/webhooks/{hook.id}/test",
        json={"arguments": {"order_id": "A1"}},
        headers=headers,
    )
    second = await client.post(
        f"/api/webhooks/{hook.id}/test",
        json={"arguments": {"order_id": "A1"}},
        headers=headers,
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 429
    assert second.headers["Retry-After"] == "3600"
