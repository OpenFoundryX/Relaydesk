import sqlalchemy as sa

from relaydesk.config import get_settings
from relaydesk.models.ai_call import AiCall, AiOutcome
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


async def test_the_per_ip_cap_bounds_how_many_questions_are_answered(
    client, db_session, monkeypatch
) -> None:
    """I4: the sibling `submit` route caps per client IP as well as per key
    (spec: an unattested identifier needs the other axis), because the key
    is public -- anyone who views the customer's page source can use it.
    Before this fix `ask` capped only per key, so one caller could consume
    a whole workspace's hourly allowance alone.

    The per-key cap is set high and the per-IP cap low, and two different
    widget keys in the same workspace are used for the three calls: if the
    cap this test is tripping were still keyed only on the widget key,
    switching keys for the third call would reset the count and it would
    succeed. The test client's peer address is the same for every call
    here, so this only shows a real cap if it is genuinely per-address.
    """
    get_settings.cache_clear()
    monkeypatch.setenv("WIDGET_ASK_IP_HOURLY_CAP", "2")
    monkeypatch.setenv("WIDGET_ASK_HOURLY_CAP", "100")

    workspace = await make_workspace(db_session)
    key_a = await widget_keys.create(db_session, workspace.id, "Site A")
    key_b = await widget_keys.create(db_session, workspace.id, "Site B")
    await db_session.commit()

    for _ in range(2):
        response = await client.post(
            f"/api/widget/{key_a.key}/ask", json={"question": "how do refunds work"}
        )
        assert response.status_code == 200

    third = await client.post(
        f"/api/widget/{key_b.key}/ask", json={"question": "how do refunds work"}
    )
    assert third.status_code == 200  # Silent, exactly like the first two.

    count = await db_session.scalar(sa.select(sa.func.count()).select_from(AiCall))
    assert count == 2  # The third call, on a different key, never reached ai_answers.answer.

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


async def test_a_long_message_and_transcript_still_files_the_ticket(
    client, db_session
) -> None:
    """The transcript must yield to the message, never the other way round.

    `tickets.submit` re-validates the combined body against
    `ticket_message_max_chars` (10,000): a 7,000-character message plus an
    untrimmed 5,000-character transcript would blow straight through that
    and reject the whole ticket. The transcript is the one that gives way
    -- the visitor wrote the message, the widget only generated the
    transcript -- so the ticket must still be filed.
    """
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.commit()

    response = await client.post(
        f"/api/widget/{key.key}/tickets",
        data={
            "email": "wren@lantern.co",
            "message": "M" * 7000,
            "transcript": "T" * 5000,
        },
    )
    assert response.status_code == 201, response.text

    count = await db_session.scalar(
        sa.select(sa.func.count()).select_from(Conversation)
    )
    assert count == 1


async def test_no_room_at_all_drops_the_transcript_but_still_files_the_ticket(
    client, db_session
) -> None:
    """A message that alone fills the ticket cap leaves nothing to append.

    Losing the transcript is a degradation the agent can live without;
    losing the ticket outright is a failure. A message at the cap must
    still be accepted, with the transcript silently dropped.
    """
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.commit()

    response = await client.post(
        f"/api/widget/{key.key}/tickets",
        data={
            "email": "wren@lantern.co",
            "message": "M" * get_settings().ticket_message_max_chars,
            "transcript": "Visitor: how do refunds work",
        },
    )
    assert response.status_code == 201, response.text

    body = await db_session.scalar(sa.select(Message.body))
    assert "how do refunds work" not in body


async def test_transcript_truncation_keeps_the_tail(client, db_session) -> None:
    """The turn just before a visitor gives up is what the agent needs to
    see; the oldest part of a long conversation is the safest to drop."""
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.commit()

    transcript = "HEADMARKER" + ("A" * 5000) + "TAILMARKER"

    response = await client.post(
        f"/api/widget/{key.key}/tickets",
        data={
            "email": "wren@lantern.co",
            "message": "This did not help.",
            "transcript": transcript,
        },
    )
    assert response.status_code == 201, response.text

    body = await db_session.scalar(sa.select(Message.body))
    assert "TAILMARKER" in body
    assert "HEADMARKER" not in body


async def test_an_escalation_writes_an_ai_call_row(client, db_session) -> None:
    """Without this row, deflection cannot tell "asked the AI, gave up,
    asked a human" apart from "never asked at all" -- most of the point of
    measuring it."""
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

    outcome = await db_session.scalar(sa.select(AiCall.outcome))
    assert outcome == AiOutcome.escalated


async def test_a_ticket_with_no_transcript_writes_no_ai_call_row(
    client, db_session
) -> None:
    """A visitor who never touched the AI must not be counted as one who
    gave up on it."""
    workspace = await make_workspace(db_session)
    key = await widget_keys.create(db_session, workspace.id, "Site")
    await db_session.commit()

    response = await client.post(
        f"/api/widget/{key.key}/tickets",
        data={"email": "wren@lantern.co", "message": "Where is my order?"},
    )
    assert response.status_code == 201

    count = await db_session.scalar(sa.select(sa.func.count()).select_from(AiCall))
    assert count == 0
