from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models import ConversationStatus
from tests.factories import (
    make_conversation,
    make_label,
    make_member,
    make_workspace,
    sign_in,
)


async def test_list_returns_the_console_shape(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    await make_conversation(db_session, workspace, assignee=user, with_draft=True)
    headers = await sign_in(client, db_session, user.email)

    response = await client.get("/api/conversations?status=open", headers=headers)

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["subject"] == "Checkout fails with a 402"
    assert item["customerName"] == "Priya Raman"
    assert item["customerEmail"] == "priya@northwind.io"
    assert item["channel"] == "email"
    assert item["status"] == "open"
    assert item["priority"] == "urgent"
    assert item["assignee"] == "Nilesh Pant"
    assert item["assigneeId"] == str(user.id)
    assert item["hasDraft"] is True
    assert item["summaryState"] == "none"
    assert item["summary"] is None
    assert item["number"] == 1
    assert item["age"] == "12m"
    assert item["labelIds"] == []


async def test_list_filters_by_status(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    await make_conversation(db_session, workspace)
    await make_conversation(db_session, workspace, status=ConversationStatus.resolved)
    headers = await sign_in(client, db_session, user.email)

    open_items = (
        await client.get("/api/conversations?status=open", headers=headers)
    ).json()
    resolved = (
        await client.get("/api/conversations?status=resolved", headers=headers)
    ).json()

    assert len(open_items["items"]) == 1
    assert len(resolved["items"]) == 1


async def test_counts_cover_every_status_and_drafts(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    await make_conversation(db_session, workspace, with_draft=True)
    await make_conversation(db_session, workspace, status=ConversationStatus.pending)
    headers = await sign_in(client, db_session, user.email)

    body = (await client.get("/api/conversations/counts", headers=headers)).json()

    counts = {entry["status"]: entry["count"] for entry in body["statuses"]}
    assert counts["open"] == 1
    assert counts["pending"] == 1
    assert counts["trash"] == 0
    assert body["drafts"] == 1


async def test_detail_messages_activity_and_draft(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    conversation = await make_conversation(db_session, workspace, with_draft=True)
    headers = await sign_in(client, db_session, user.email)
    base = f"/api/conversations/{conversation.id}"

    detail = await client.get(base, headers=headers)
    messages = await client.get(f"{base}/messages", headers=headers)
    draft = await client.get(f"{base}/draft", headers=headers)
    activity = await client.get(f"{base}/activity", headers=headers)

    assert detail.status_code == 200
    assert messages.json()[0]["role"] == "customer"
    assert messages.json()[0]["author"] == "Priya Raman"
    assert draft.json()["body"].startswith("Hi Priya")
    assert activity.status_code == 200


async def test_missing_draft_is_a_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    conversation = await make_conversation(db_session, workspace)
    headers = await sign_in(client, db_session, user.email)

    response = await client.get(
        f"/api/conversations/{conversation.id}/draft", headers=headers
    )

    assert response.status_code == 404


async def test_labels_are_listed_and_created(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    await make_label(db_session, workspace)
    headers = await sign_in(client, db_session, user.email)

    listed = (await client.get("/api/labels", headers=headers)).json()
    created = await client.post("/api/labels", headers=headers, json={"name": "Bug"})

    assert [entry["name"] for entry in listed] == ["Billing"]
    assert created.status_code == 201
    assert created.json()["color"] in {"citron", "slate", "amber", "rose", "sky"}


async def test_creating_a_duplicate_label_returns_the_existing_one(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    label = await make_label(db_session, workspace)
    headers = await sign_in(client, db_session, user.email)

    response = await client.post(
        "/api/labels", headers=headers, json={"name": "billing"}
    )

    assert response.status_code == 201
    assert response.json()["id"] == str(label.id)
