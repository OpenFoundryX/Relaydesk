"""Cross-workspace access must be indistinguishable from nonexistence.

This is the failure mode with the worst consequences and the least chance
of being noticed by hand, so every workspace-scoped route is checked.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import (
    make_conversation,
    make_label,
    make_member,
    make_workspace,
    sign_in,
)


@pytest.fixture
async def two_workspaces(client: AsyncClient, db_session: AsyncSession):
    mine = await make_workspace(db_session, slug="chronon")
    theirs = await make_workspace(db_session, slug="northwind")
    me = await make_member(db_session, mine, email="me@relaydesk.dev", name="Me Myself")
    await make_member(db_session, theirs, email="them@northwind.io", name="Them Other")
    foreign = await make_conversation(db_session, theirs, with_draft=True)
    foreign_label = await make_label(db_session, theirs, name="TheirLabel")
    headers = await sign_in(client, db_session, me.email)
    return headers, foreign, foreign_label


async def test_foreign_conversation_is_not_listed(client, two_workspaces) -> None:
    headers, _, _ = two_workspaces

    body = (await client.get("/api/conversations?status=open", headers=headers)).json()

    assert body["items"] == []


@pytest.mark.parametrize("suffix", ["", "/messages", "/draft", "/activity"])
async def test_foreign_conversation_reads_return_404(
    client, two_workspaces, suffix
) -> None:
    headers, foreign, _ = two_workspaces

    response = await client.get(
        f"/api/conversations/{foreign.id}{suffix}", headers=headers
    )

    assert response.status_code == 404


async def test_foreign_label_is_not_listed(client, two_workspaces) -> None:
    headers, _, _ = two_workspaces

    body = (await client.get("/api/labels", headers=headers)).json()

    assert body == []


async def test_counts_exclude_other_workspaces(client, two_workspaces) -> None:
    headers, _, _ = two_workspaces

    body = (await client.get("/api/conversations/counts", headers=headers)).json()

    assert all(entry["count"] == 0 for entry in body["statuses"])
    assert body["drafts"] == 0


async def test_creating_a_label_matching_a_foreign_name_is_not_a_collision(
    client, two_workspaces
) -> None:
    headers, _, foreign_label = two_workspaces

    response = await client.post(
        "/api/labels", headers=headers, json={"name": foreign_label.name}
    )

    assert response.status_code == 201
    assert response.json()["id"] != str(foreign_label.id)
    assert response.json()["name"] == foreign_label.name
