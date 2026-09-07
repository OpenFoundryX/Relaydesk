from datetime import UTC, datetime, timedelta

from relaydesk.config import get_settings
from relaydesk.models import ApiKeyScope
from relaydesk.services import api_keys
from tests.factories import make_conversation, make_workspace


async def mint(db_session, workspace, scopes, **kwargs):
    token, key = await api_keys.mint(
        db_session,
        workspace.id,
        name=kwargs.pop("name", "Integration"),
        scopes=scopes,
        created_by_user_id=None,
        **kwargs,
    )
    return token, key


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_a_call_with_no_key_is_refused(client) -> None:
    response = await client.get("/v1/conversations")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_a_call_with_an_unknown_key_is_refused(client) -> None:
    response = await client.get(
        "/v1/conversations", headers=auth("rd_never-minted-anywhere")
    )

    assert response.status_code == 401


async def test_a_revoked_key_is_refused(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    token, key = await mint(db_session, workspace, [ApiKeyScope.conversations_read])
    await api_keys.revoke(db_session, workspace.id, key.id)

    response = await client.get("/v1/conversations", headers=auth(token))

    assert response.status_code == 401


async def test_an_expired_key_is_refused(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    token, _ = await mint(
        db_session,
        workspace,
        [ApiKeyScope.conversations_read],
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )

    response = await client.get("/v1/conversations", headers=auth(token))

    assert response.status_code == 401


async def test_a_key_without_the_scope_is_refused_and_told_which(
    client, db_session
) -> None:
    workspace = await make_workspace(db_session)
    token, _ = await mint(db_session, workspace, [ApiKeyScope.labels_read])

    response = await client.get("/v1/conversations", headers=auth(token))

    assert response.status_code == 403
    body = response.json()["error"]
    assert body["code"] == "forbidden"
    assert "conversations:read" in body["message"]


async def test_a_key_with_the_scope_is_allowed(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    token, _ = await mint(db_session, workspace, [ApiKeyScope.conversations_read])

    response = await client.get("/v1/conversations", headers=auth(token))

    assert response.status_code == 200


async def test_a_key_cannot_see_another_workspaces_conversation(
    client, db_session
) -> None:
    ours = await make_workspace(db_session, slug="ours")
    theirs = await make_workspace(db_session, slug="theirs")
    hidden = await make_conversation(db_session, theirs)
    token, _ = await mint(db_session, ours, [ApiKeyScope.conversations_read])

    response = await client.get(
        f"/v1/conversations/{hidden.id}", headers=auth(token)
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_every_response_carries_the_rate_limit_headers(
    client, db_session
) -> None:
    workspace = await make_workspace(db_session)
    token, _ = await mint(db_session, workspace, [ApiKeyScope.conversations_read])

    response = await client.get("/v1/conversations", headers=auth(token))

    limit = get_settings().api_key_rate_limit_per_minute
    assert response.headers["x-ratelimit-limit"] == str(limit)
    assert int(response.headers["x-ratelimit-remaining"]) == limit - 1


async def test_a_key_over_its_limit_is_refused_with_retry_after(
    client, db_session, monkeypatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "api_key_rate_limit_per_minute", 2)
    workspace = await make_workspace(db_session)
    token, _ = await mint(db_session, workspace, [ApiKeyScope.conversations_read])

    for _ in range(2):
        assert (
            await client.get("/v1/conversations", headers=auth(token))
        ).status_code == 200

    response = await client.get("/v1/conversations", headers=auth(token))

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "too_many_requests"
    assert response.headers["retry-after"] == "60"


async def test_the_console_surface_does_not_accept_an_api_key(
    client, db_session
) -> None:
    """A key is not a session. ``/api`` stays session-only (spec D2)."""
    workspace = await make_workspace(db_session)
    token, _ = await mint(db_session, workspace, [ApiKeyScope.conversations_read])

    response = await client.get("/api/conversations", headers=auth(token))

    assert response.status_code == 401
