from relaydesk.models import Role
from relaydesk.models.ai_config import AiConfig
from tests.factories import make_member, make_workspace, sign_in


async def admin_headers(client, db_session, workspace):
    await make_member(db_session, workspace, email="admin@relaydesk.dev")
    await db_session.commit()
    return await sign_in(client, db_session, "admin@relaydesk.dev")


async def agent_headers(client, db_session, workspace):
    await make_member(
        db_session, workspace, email="agent@relaydesk.dev", role=Role.agent
    )
    await db_session.commit()
    return await sign_in(client, db_session, "agent@relaydesk.dev")


async def test_the_key_is_never_returned(client, db_session) -> None:
    """Write-only means write-only: a masked suffix, never the value."""
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)

    await client.put(
        "/api/ai-config",
        json={"enabled": True, "apiKey": "sk-ant-secret-tail1234"},
        headers=headers,
    )
    read = await client.get("/api/ai-config", headers=headers)

    assert read.status_code == 200
    assert "sk-ant-secret-tail1234" not in read.text
    assert read.json()["keySuffix"] == "1234"


async def test_an_agent_cannot_read_or_write_it(client, db_session) -> None:
    workspace = await make_workspace(db_session)
    headers = await agent_headers(client, db_session, workspace)

    assert (await client.get("/api/ai-config", headers=headers)).status_code == 403
    assert (
        await client.put("/api/ai-config", json={"enabled": True}, headers=headers)
    ).status_code == 403


async def test_omitting_the_key_leaves_the_installed_one_alone(client, db_session) -> None:
    """Editing the budget must not silently discard the key."""
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)
    await client.put(
        "/api/ai-config", json={"enabled": True, "apiKey": "sk-keep-me-9999"}, headers=headers
    )

    await client.put("/api/ai-config", json={"dailyTokenBudget": 50_000}, headers=headers)
    read = await client.get("/api/ai-config", headers=headers)

    assert read.json()["keySuffix"] == "9999"
    assert read.json()["dailyTokenBudget"] == 50_000


async def test_write_route_really_commits(client, db_session, commit_spy) -> None:
    """``write_route`` must commit, not just flush -- see ai_configs.py.

    `commit_spy` is the only thing in this file that can tell the two
    apart: `client` hands the route this exact `db_session`, so a bare
    flush is already visible to every other assertion here, committed or
    not -- the shared-session fixture cannot distinguish them any other way.
    """
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)
    commit_spy.clear()  # admin_headers' own sign-in commits too.

    response = await client.put(
        "/api/ai-config", json={"enabled": True}, headers=headers
    )

    assert response.status_code == 200, response.text
    assert len(commit_spy) >= 1


async def test_an_unconfigured_workspace_reads_the_real_defaults(
    client, db_session
) -> None:
    """A workspace that has never configured AI sees what it would get.

    SQLAlchemy column defaults are applied at INSERT, not at construction,
    so answering this from an unsaved `AiConfig` would return None for
    every field and render the screen blank -- the same trap that once let
    a `for_config` test pass with a real key in place.
    """
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)

    response = await client.get("/api/ai-config", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "anthropic"
    assert body["model"] == "claude-opus-5"
    assert body["dailyTokenBudget"] == 200_000
    assert body["enabled"] is False
    assert body["keySuffix"] is None


async def test_reading_does_not_create_a_row(client, db_session) -> None:
    """A settings screen is a read. A monitor polling it must not write."""
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)

    await client.get("/api/ai-config", headers=headers)

    assert await db_session.get(AiConfig, workspace.id) is None


async def test_a_short_key_is_not_echoed_back_as_its_own_suffix(
    client, db_session
) -> None:
    """`keySuffix` must identify a key, never reveal one.

    The last four characters of a two-character key are the key. Real
    provider keys are far longer, so this guards a mistake rather than an
    attack -- but "never returned" is the promise this screen exists to
    keep, and a promise with an exception is a different promise.
    """
    workspace = await make_workspace(db_session)
    headers = await admin_headers(client, db_session, workspace)

    response = await client.put(
        "/api/ai-config", json={"apiKey": "ab"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["keySuffix"] is None
