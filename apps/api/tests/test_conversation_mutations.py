from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import (
    make_conversation,
    make_label,
    make_member,
    make_workspace,
    sign_in,
)


async def setup(client: AsyncClient, session: AsyncSession):
    workspace = await make_workspace(session)
    user = await make_member(session, workspace)
    conversation = await make_conversation(session, workspace, with_draft=True)
    headers = await sign_in(client, session, user.email)
    return workspace, user, conversation, headers


async def test_status_change_records_activity(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, conversation, headers = await setup(client, db_session)

    response = await client.patch(
        f"/api/conversations/{conversation.id}",
        headers=headers,
        json={"status": "resolved"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "resolved"

    activity = (
        await client.get(
            f"/api/conversations/{conversation.id}/activity", headers=headers
        )
    ).json()
    assert activity[0]["kind"] == "status"
    assert activity[0]["verb"] == "marked this as"
    assert activity[0]["value"] == "Resolved"
    assert activity[0]["status"] == "resolved"
    assert activity[0]["actor"] == "Nilesh Pant"


async def test_setting_the_same_status_records_nothing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, conversation, headers = await setup(client, db_session)

    await client.patch(
        f"/api/conversations/{conversation.id}",
        headers=headers,
        json={"status": "open"},
    )

    activity = (
        await client.get(
            f"/api/conversations/{conversation.id}/activity", headers=headers
        )
    ).json()
    assert activity == []


async def test_priority_and_assignee_changes(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, user, conversation, headers = await setup(client, db_session)

    await client.patch(
        f"/api/conversations/{conversation.id}",
        headers=headers,
        json={"priority": "low"},
    )
    assigned = await client.patch(
        f"/api/conversations/{conversation.id}",
        headers=headers,
        json={"assigneeId": str(user.id)},
    )

    assert assigned.json()["assignee"] == "Nilesh Pant"
    assert assigned.json()["assigneeId"] == str(user.id)

    activity = (
        await client.get(
            f"/api/conversations/{conversation.id}/activity", headers=headers
        )
    ).json()
    kinds = [event["kind"] for event in activity]
    assert "assignee" in kinds and "priority" in kinds


async def test_unassigning_records_the_right_verb(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, user, conversation, headers = await setup(client, db_session)
    await client.patch(
        f"/api/conversations/{conversation.id}",
        headers=headers,
        json={"assigneeId": str(user.id)},
    )

    await client.patch(
        f"/api/conversations/{conversation.id}",
        headers=headers,
        json={"assigneeId": None},
    )

    activity = (
        await client.get(
            f"/api/conversations/{conversation.id}/activity", headers=headers
        )
    ).json()
    assert activity[0]["verb"] == "unassigned this from"
    assert activity[0]["value"] == "Nilesh Pant"


async def test_labels_attach_and_detach_idempotently(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    workspace, _, conversation, headers = await setup(client, db_session)
    label = await make_label(db_session, workspace)
    path = f"/api/conversations/{conversation.id}/labels/{label.id}"

    assert (await client.put(path, headers=headers)).status_code == 200
    assert (await client.put(path, headers=headers)).status_code == 200
    detail = (
        await client.get(f"/api/conversations/{conversation.id}", headers=headers)
    ).json()
    assert detail["labelIds"] == [str(label.id)]

    assert (await client.delete(path, headers=headers)).status_code == 200
    detail = (
        await client.get(f"/api/conversations/{conversation.id}", headers=headers)
    ).json()
    assert detail["labelIds"] == []


async def test_reply_appends_a_message_and_clears_the_draft(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, conversation, headers = await setup(client, db_session)

    response = await client.post(
        f"/api/conversations/{conversation.id}/replies",
        headers=headers,
        json={"body": "On it — checking now.", "resolve": True},
    )

    assert response.status_code == 201
    messages = (
        await client.get(
            f"/api/conversations/{conversation.id}/messages", headers=headers
        )
    ).json()
    assert messages[-1]["body"] == "On it — checking now."
    assert messages[-1]["role"] == "agent"
    assert messages[-1]["author"] == "Nilesh Pant"

    detail = (
        await client.get(f"/api/conversations/{conversation.id}", headers=headers)
    ).json()
    assert detail["hasDraft"] is False
    assert detail["status"] == "resolved"
    assert detail["unread"] is False
    assert detail["preview"] == "On it — checking now."


async def test_discarding_a_draft(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, conversation, headers = await setup(client, db_session)

    response = await client.delete(
        f"/api/conversations/{conversation.id}/draft", headers=headers
    )

    assert response.status_code == 204
    detail = (
        await client.get(f"/api/conversations/{conversation.id}", headers=headers)
    ).json()
    assert detail["hasDraft"] is False


async def test_bulk_status_change(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    workspace, _, first, headers = await setup(client, db_session)
    second = await make_conversation(db_session, workspace)

    response = await client.post(
        "/api/conversations/bulk-status",
        headers=headers,
        json={"ids": [str(first.id), str(second.id)], "status": "trash"},
    )

    assert response.status_code == 204
    counts = (await client.get("/api/conversations/counts", headers=headers)).json()
    by_status = {entry["status"]: entry["count"] for entry in counts["statuses"]}
    assert by_status["trash"] == 2


async def test_mutating_a_foreign_conversation_is_a_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, _, headers = await setup(client, db_session)
    other = await make_workspace(db_session, slug="northwind")
    await make_member(db_session, other, email="them@northwind.io", name="Them Other")
    foreign = await make_conversation(db_session, other)

    response = await client.patch(
        f"/api/conversations/{foreign.id}", headers=headers, json={"status": "resolved"}
    )

    assert response.status_code == 404
