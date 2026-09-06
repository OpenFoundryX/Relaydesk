import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.config import get_settings
from relaydesk.db.session import get_session
from relaydesk.main import app
from relaydesk.models.conversation import Conversation
from relaydesk.models.rate_limit import RateLimitHit
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
    db_session: AsyncSession, client, monkeypatch
) -> None:
    """The IP cap, the per-email cap, and the honeypot are three different
    abuse controls. An attacker who can tell, from the response alone,
    which one fired learns how to tune around it -- so this checks all
    three pairwise, not just the wording of one of them.
    """
    await make_workspace(db_session, slug="chronon")
    await db_session.commit()

    # A genuine success, to compare the honeypot's fake one against.
    genuine = await client.post("/api/public/chronon/tickets", data=_form())
    assert genuine.status_code == 201

    # The honeypot: same 201, same body -- nothing to tell them apart.
    honeypot = await client.post(
        "/api/public/chronon/tickets", data=_form(company="Acme Inc")
    )
    assert honeypot.status_code == 201
    assert honeypot.json() == genuine.json()

    # Three more successes (distinct emails), then the IP cap fires on the
    # sixth call from this client.
    for index in range(3):
        ok = await client.post(
            "/api/public/chronon/tickets",
            data=_form(email=f"ada{index}@example.dev"),
        )
        assert ok.status_code == 201
    ip_capped = await client.post(
        "/api/public/chronon/tickets", data=_form(email="ada99@example.dev")
    )
    assert ip_capped.status_code == 429

    # Lift the IP cap out of the way so the per-email cap -- a much higher
    # threshold (20/hour) -- can be reached on its own from this same
    # client without the IP cap intercepting it first.
    monkeypatch.setattr(get_settings(), "ticket_ip_hourly_cap", 10_000)
    for _ in range(20):
        flood = await client.post(
            "/api/public/chronon/tickets", data=_form(email="flood@example.dev")
        )
        assert flood.status_code == 201
    email_capped = await client.post(
        "/api/public/chronon/tickets", data=_form(email="flood@example.dev")
    )
    assert email_capped.status_code == 429

    # The two refusals must be identical -- same status, same body -- and
    # neither may name a control.
    assert email_capped.status_code == ip_capped.status_code
    assert email_capped.json() == ip_capped.json()
    for refusal in (ip_capped, email_capped):
        body = refusal.text.lower()
        for leaked in ("ip", "address", "rate", "honeypot", "cap"):
            assert leaked not in body


async def test_the_rate_limit_charge_survives_the_session_closing(
    db_session: AsyncSession,
) -> None:
    """`ratelimit.check` only flushes a hit; nothing persists it across a
    request boundary unless something commits it. The `client` fixture
    would hide a missing commit here: every request in a test shares the
    same still-open `db_session` (see `tests/conftest.py`), so a
    flushed-but-uncommitted row from one `client.post()` stays visible to
    the next regardless of whether anything ever committed it -- which is
    exactly why a plain second `client.post()` cannot catch this bug.

    Production's `get_session` instead opens a fresh session per request
    and closes it -- rolling back anything that session never committed --
    when the request ends. To catch a missing commit honestly, this drives
    the route through its own request-scoped session (bound to the same
    connection as `db_session`, so it can see the workspace created here),
    closes that session exactly as `get_session` would at the end of a
    real request, and only then checks -- from `db_session`, a different
    session entirely -- whether the rate-limit hit survived.
    """
    await make_workspace(db_session, slug="chronon")
    await db_session.commit()
    connection = await db_session.connection()

    request_session = AsyncSession(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    app.dependency_overrides[get_session] = lambda: request_session
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as isolated_client:
            # The honeypot path: the exact request shape that used to
            # discard its charge, since it returns before the route's
            # final `session.commit()` is ever reached.
            response = await isolated_client.post(
                "/api/public/chronon/tickets", data=_form(company="Acme Inc")
            )
        assert response.status_code == 201
    finally:
        await request_session.close()
        app.dependency_overrides.pop(get_session, None)

    count = await db_session.scalar(
        sa.select(sa.func.count()).select_from(RateLimitHit)
    )
    assert count == 1
