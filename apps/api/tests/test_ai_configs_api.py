from relaydesk.models import Role
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
