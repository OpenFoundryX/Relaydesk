import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.models.conversation import Conversation
from tests.factories import make_workspace


def _form(**overrides) -> dict:
    form = {
        "email": "ada@example.dev",
        "name": "Ada",
        "subject": "Refund please",
        "message": "My order never arrived.",
        "company": "",
    }
    form.update(overrides)
    return form


async def test_a_submission_creates_a_ticket(db_session: AsyncSession, client) -> None:
    await make_workspace(db_session, slug="chronon")
    await db_session.commit()

    response = await client.post("/api/public/chronon/tickets", data=_form())

    assert response.status_code == 201
    conversation = await db_session.scalar(sa.select(Conversation))
    assert conversation is not None


async def test_the_response_carries_no_ticket_identifier(
    db_session: AsyncSession, client
) -> None:
    """The submitter gets confirmation, not a handle to probe the inbox with."""
    await make_workspace(db_session, slug="chronon")
    await db_session.commit()

    response = await client.post("/api/public/chronon/tickets", data=_form())

    body = response.json()
    assert "id" not in body
    assert "number" not in body


async def test_an_unknown_workspace_is_a_404(db_session: AsyncSession, client) -> None:
    await make_workspace(db_session, slug="chronon")
    await db_session.commit()

    response = await client.post("/api/public/nobody/tickets", data=_form())

    assert response.status_code == 404


async def test_a_reserved_label_is_a_404(db_session: AsyncSession, client) -> None:
    await make_workspace(db_session, slug="chronon")
    await db_session.commit()

    response = await client.post("/api/public/api/tickets", data=_form())

    assert response.status_code == 404


async def test_a_filled_honeypot_is_accepted_but_creates_nothing(
    db_session: AsyncSession, client
) -> None:
    """A bot must not learn it was caught, so the response is the same 201 a
    real submission gets -- and no ticket exists behind it."""
    await make_workspace(db_session, slug="chronon")
    await db_session.commit()

    response = await client.post(
        "/api/public/chronon/tickets", data=_form(company="Acme Inc")
    )

    assert response.status_code == 201
    count = await db_session.scalar(
        sa.select(sa.func.count()).select_from(Conversation)
    )
    assert count == 0


async def test_the_ip_cap_refuses_the_call_over_the_limit(
    db_session: AsyncSession, client
) -> None:
    await make_workspace(db_session, slug="chronon")
    await db_session.commit()

    for index in range(5):
        ok = await client.post(
            "/api/public/chronon/tickets",
            data=_form(email=f"ada{index}@example.dev"),
        )
        assert ok.status_code == 201

    refused = await client.post(
        "/api/public/chronon/tickets", data=_form(email="ada5@example.dev")
    )
    assert refused.status_code == 429


async def test_a_refusal_does_not_say_which_control_fired(
    db_session: AsyncSession, client
) -> None:
    """An attacker who learns which limit they hit learns how to tune around
    it."""
    await make_workspace(db_session, slug="chronon")
    await db_session.commit()

    for index in range(5):
        await client.post(
            "/api/public/chronon/tickets",
            data=_form(email=f"ada{index}@example.dev"),
        )
    refused = await client.post(
        "/api/public/chronon/tickets", data=_form(email="ada5@example.dev")
    )

    body = refused.text.lower()
    for leaked in ("ip", "address", "rate", "honeypot", "cap"):
        assert leaked not in body
