from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models import ConversationStatus, Priority, SavedView
from tests.factories import make_conversation, make_member, make_workspace, sign_in


async def test_views_report_their_counts(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    await make_conversation(db_session, workspace, priority=Priority.urgent)
    await make_conversation(db_session, workspace, assignee=user, priority=Priority.low)
    await make_conversation(db_session, workspace, status=ConversationStatus.pending)
    db_session.add_all(
        [
            SavedView(
                workspace_id=workspace.id,
                name="Urgent & unassigned",
                filters={
                    "priority": "urgent",
                    "assignee": "unassigned",
                    "status": "open",
                },
                position=0,
            ),
            SavedView(
                workspace_id=workspace.id,
                name="Assigned to me",
                filters={"assignee": "me"},
                position=1,
            ),
            SavedView(
                workspace_id=workspace.id,
                name="Waiting on customer",
                filters={"status": "pending"},
                position=2,
            ),
        ]
    )
    await db_session.commit()
    headers = await sign_in(client, db_session, user.email)

    body = (await client.get("/api/views", headers=headers)).json()

    counts = {entry["name"]: entry["count"] for entry in body}
    assert counts["Urgent & unassigned"] == 1
    assert counts["Assigned to me"] == 1
    assert counts["Waiting on customer"] == 1


async def test_listing_by_view_applies_its_filters(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    await make_conversation(db_session, workspace, priority=Priority.urgent)
    await make_conversation(db_session, workspace, assignee=user, priority=Priority.low)
    view = SavedView(
        workspace_id=workspace.id,
        name="Urgent & unassigned",
        filters={"priority": "urgent", "assignee": "unassigned", "status": "open"},
    )
    db_session.add(view)
    await db_session.commit()
    headers = await sign_in(client, db_session, user.email)

    body = (
        await client.get(f"/api/conversations?viewId={view.id}", headers=headers)
    ).json()

    assert len(body["items"]) == 1
    assert body["items"][0]["priority"] == "urgent"


async def test_a_views_reported_count_matches_its_list_length(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    await make_conversation(db_session, workspace, priority=Priority.urgent)
    await make_conversation(db_session, workspace, priority=Priority.urgent)
    await make_conversation(db_session, workspace, priority=Priority.low)
    view = SavedView(
        workspace_id=workspace.id,
        name="Urgent tickets",
        filters={"priority": "urgent"},
    )
    db_session.add(view)
    await db_session.commit()
    headers = await sign_in(client, db_session, user.email)

    views_body = (await client.get("/api/views", headers=headers)).json()
    reported_count = next(
        entry["count"] for entry in views_body if entry["id"] == str(view.id)
    )
    conversations_body = (
        await client.get(f"/api/conversations?viewId={view.id}", headers=headers)
    ).json()

    assert reported_count == 2
    assert len(conversations_body["items"]) == reported_count


async def test_a_foreign_view_is_a_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    other = await make_workspace(db_session, slug="northwind")
    view = SavedView(workspace_id=other.id, name="Theirs", filters={})
    db_session.add(view)
    await db_session.commit()
    headers = await sign_in(client, db_session, user.email)

    response = await client.get(f"/api/conversations?viewId={view.id}", headers=headers)

    assert response.status_code == 404


async def test_a_view_with_an_unrecognised_status_still_excludes_trash(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Falling through to "no status filter at all" would silently surface
    trashed conversations."""
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    await make_conversation(db_session, workspace)
    await make_conversation(
        db_session,
        workspace,
        subject="Junk",
        status=ConversationStatus.trash,
        contact_email="sam@example.com",
        contact_name="Sam Rowe",
    )
    view = SavedView(
        workspace_id=workspace.id,
        name="Stale filter",
        filters={"status": "archived"},
        position=0,
    )
    db_session.add(view)
    await db_session.commit()
    headers = await sign_in(client, db_session, user.email)

    listed = await client.get(f"/api/conversations?viewId={view.id}", headers=headers)
    counted = await client.get("/api/views", headers=headers)

    assert listed.status_code == 200
    subjects = [entry["subject"] for entry in listed.json()["items"]]
    assert "Junk" not in subjects
    assert len(subjects) == 1
    assert next(
        entry["count"] for entry in counted.json() if entry["id"] == str(view.id)
    ) == 1
