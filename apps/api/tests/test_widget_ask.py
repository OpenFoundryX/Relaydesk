import sqlalchemy as sa

from relaydesk.config import get_settings
from relaydesk.models.ai_call import AiCall
from relaydesk.models.conversation import Conversation
from relaydesk.models.message import Message
from relaydesk.schemas.widget import QUESTION_MAX_CHARS
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


async def test_an_overlong_question_is_rejected(client, db_session) -> None:
    """The one field billed per call must not be trustable as unbounded."""
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.commit()

    response = await client.post(
        f"/api/widget/{key.key}/ask",
        json={"question": "a" * (QUESTION_MAX_CHARS + 1)},
    )

    assert response.status_code == 422


async def test_the_hourly_cap_bounds_how_many_questions_are_answered(
    client, db_session, monkeypatch
) -> None:
    """Cost is the abuse surface on this route (spec D5): a caller within
    the cap must still be answered (or degraded on its own merits), and a
    caller past it must never reach `ai_answers.answer` at all -- silently,
    the same as every other refusal on this route. A rate-limited response
    and any other degrade reason render identically, so the only place this
    is observable from outside is the audit table `ai_answers.answer`
    writes to on every call it actually makes."""
    get_settings.cache_clear()
    monkeypatch.setenv("WIDGET_ASK_HOURLY_CAP", "2")

    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.commit()

    for _ in range(2):
        response = await client.post(
            f"/api/widget/{key.key}/ask", json={"question": "how do refunds work"}
        )
        assert response.status_code == 200

    third = await client.post(
        f"/api/widget/{key.key}/ask", json={"question": "how do refunds work"}
    )
    assert third.status_code == 200  # Silent, exactly like the first two.

    count = await db_session.scalar(sa.select(sa.func.count()).select_from(AiCall))
    assert count == 2  # The third call never reached `ai_answers.answer`.

    get_settings.cache_clear()


async def test_a_resolved_question_writes_no_conversation(client, db_session) -> None:
    """An inbox full of questions the AI answered is a triage problem."""
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.commit()

    await client.post(f"/api/widget/{key.key}/ask", json={"question": "refund"})

    count = await db_session.scalar(
        sa.select(sa.func.count()).select_from(Conversation)
    )
    assert count == 0


async def test_an_escalated_question_carries_its_transcript(client, db_session) -> None:
    """The agent must see what the visitor was already told."""
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.commit()

    response = await client.post(
        f"/api/widget/{key.key}/tickets",
        data={
            "email": "wren@lantern.co",
            "message": "This did not help.",
            "transcript": "Visitor: how do refunds work\nAssistant: Within 14 days.",
        },
    )
    assert response.status_code == 201

    body = await db_session.scalar(sa.select(Message.body))
    assert "how do refunds work" in body
    assert "This did not help." in body
