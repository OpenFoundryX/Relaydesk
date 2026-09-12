from relaydesk.services import widget_keys
from tests.factories import make_workspace


async def test_an_unconfigured_workspace_degrades_rather_than_erroring(
    client, db_session
) -> None:
    """A workspace with no AI must see the widget it already had, not a 500."""
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.commit()

    response = await client.post(
        f"/api/widget/{key.key}/ask", json={"question": "how do refunds work"}
    )

    assert response.status_code == 200
    assert "degraded" in response.text


async def test_an_unknown_key_is_refused_like_every_other_widget_route(
    client, db_session
) -> None:
    response = await client.post(
        "/api/widget/rdw_" + "0" * 32 + "/ask", json={"question": "hello"}
    )
    assert response.status_code == 404
