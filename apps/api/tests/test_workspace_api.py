from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models import Role
from tests.factories import make_conversation, make_member, make_workspace, sign_in


async def test_admin_can_change_the_timezone(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    await db_session.commit()
    headers = await sign_in(client, db_session, user.email)

    response = await client.patch(
        "/api/workspace", headers=headers, json={"timezone": "Asia/Kolkata"}
    )

    assert response.status_code == 200
    await db_session.refresh(workspace)
    assert workspace.timezone == "Asia/Kolkata"


async def test_an_invalid_timezone_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A bad IANA value would 500 every conversation serializer for the
    whole workspace, so it must never reach the column."""
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    await make_conversation(db_session, workspace)
    headers = await sign_in(client, db_session, user.email)

    response = await client.patch(
        "/api/workspace", headers=headers, json={"timezone": "Mars/Olympus_Mons"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid"

    await db_session.refresh(workspace)
    assert workspace.timezone == "UTC"
    # The inbox still renders, which is the whole point of the guard.
    listed = await client.get("/api/conversations", headers=headers)
    assert listed.status_code == 200


async def test_a_traversal_style_timezone_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """``ZoneInfo`` raises ValueError rather than ZoneInfoNotFoundError for
    these, so both have to be caught."""
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace)
    headers = await sign_in(client, db_session, user.email)

    response = await client.patch(
        "/api/workspace", headers=headers, json={"timezone": "../../etc/passwd"}
    )

    assert response.status_code == 422


async def test_an_agent_cannot_patch_the_workspace(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    workspace = await make_workspace(db_session)
    user = await make_member(db_session, workspace, role=Role.agent)
    headers = await sign_in(client, db_session, user.email)

    response = await client.patch(
        "/api/workspace", headers=headers, json={"name": "Renamed"}
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    await db_session.refresh(workspace)
    assert workspace.name != "Renamed"
