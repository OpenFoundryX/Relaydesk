from relaydesk.config import get_settings
from relaydesk.services import widget_keys
from tests.factories import make_workspace


async def test_bootstrap_reports_an_empty_knowledge_base(client, db_session):
    """The day-one state: the frame must know before its first paint."""
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.commit()

    response = await client.get(f"/api/widget/{key.key}")
    assert response.status_code == 200
    body = response.json()
    assert body["articleCount"] == 0
    assert body["workspaceName"] == workspace.name


async def test_unknown_and_inactive_keys_answer_identically(client, db_session):
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await widget_keys.update(db_session, workspace.id, key.id, active=False)
    await db_session.commit()

    inactive = await client.get(f"/api/widget/{key.key}")
    unknown = await client.get("/api/widget/rdw_" + "0" * 32)

    assert inactive.status_code == unknown.status_code == 404
    assert inactive.json() == unknown.json()


async def test_bootstrap_records_that_the_embed_is_installed(client, db_session):
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.commit()

    await client.get(f"/api/widget/{key.key}")
    await db_session.refresh(key)
    assert key.last_seen_at is not None


async def test_embed_policy_refuses_when_no_origins_are_set(client, db_session):
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.commit()

    response = await client.get(f"/api/widget/{key.key}/embed-policy")
    assert response.text == "frame-ancestors 'none'"


async def test_embed_policy_answers_none_for_an_unknown_key(client, db_session):
    response = await client.get("/api/widget/rdw_" + "0" * 32 + "/embed-policy")
    assert response.status_code == 200
    assert response.text == "frame-ancestors 'none'"


async def test_knowledge_base_reads_are_capped_per_address(
    client, db_session, monkeypatch
) -> None:
    """Every write on this router has been capped since it was written and
    none of the reads were, on a door addressed only by a key that sits in
    any customer's page source.

    Per address rather than per key: a key lifted from a page is usable by
    anyone, so a per-key cap alone lets one caller spend a whole
    workspace's allowance -- the same reasoning `ask` already applies.
    """
    monkeypatch.setenv("WIDGET_KB_IP_HOURLY_CAP", "2")
    get_settings.cache_clear()

    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.commit()

    first = await client.get(f"/api/widget/{key.key}/kb")
    second = await client.get(f"/api/widget/{key.key}/kb")
    third = await client.get(f"/api/widget/{key.key}/kb")

    assert first.status_code == 200
    assert second.status_code == 200
    # Refused outright, not degraded: a list of articles is the whole
    # response, so there is no lesser answer to fall back to.
    assert third.status_code == 429

    get_settings.cache_clear()
