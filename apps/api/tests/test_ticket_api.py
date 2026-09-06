import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.config import get_settings
from relaydesk.db.session import get_session
from relaydesk.main import app
from relaydesk.models.attachment import Attachment
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


async def test_an_invalid_payload_answers_the_same_with_or_without_the_honeypot(
    db_session: AsyncSession, client
) -> None:
    """The honeypot must not be identifiable by varying one field.

    When the honeypot ran before input validation, a blank message with the
    honeypot empty was a 422 and the same blank message with the honeypot
    filled was a 201 -- so a bot posting one deliberately invalid payload
    across each candidate field read the trap's identity straight off the
    status codes, in about as many requests as the form has fields. With
    validation first, both answers are the same 422.
    """
    await make_workspace(db_session, slug="chronon")
    await db_session.commit()

    clean = await client.post(
        "/api/public/chronon/tickets", data=_form(message="   ")
    )
    trapped = await client.post(
        "/api/public/chronon/tickets", data=_form(message="   ", company="Acme Inc")
    )

    assert clean.status_code == 422
    assert trapped.status_code == clean.status_code
    assert trapped.json() == clean.json()


async def test_an_invalid_payload_answers_the_same_under_and_over_the_ip_cap(
    db_session: AsyncSession, client
) -> None:
    """The same oracle, for the IP cap rather than the honeypot.

    A limiter that ran before validation answered 429 for a payload
    validation would have rejected with 422, which tells a caller exactly
    when it crossed the cap -- and therefore what the cap is. Validation
    first means an invalid payload reads identically either side of it.
    """
    await make_workspace(db_session, slug="chronon")
    await db_session.commit()

    under = await client.post(
        "/api/public/chronon/tickets", data=_form(message="   ")
    )
    assert under.status_code == 422

    for index in range(5):
        ok = await client.post(
            "/api/public/chronon/tickets",
            data=_form(email=f"ada{index}@example.dev"),
        )
        assert ok.status_code == 201
    assert (
        await client.post("/api/public/chronon/tickets", data=_form())
    ).status_code == 429

    over = await client.post(
        "/api/public/chronon/tickets", data=_form(message="   ")
    )

    assert over.status_code == under.status_code
    assert over.json() == under.json()


async def test_a_submission_cannot_reach_another_workspaces_inbox(
    db_session: AsyncSession, client
) -> None:
    """Spec section 9: a cross-workspace attempt cannot reach another
    tenant's inbox. The workspace comes only from the resolved slug in the
    path -- never a header, never a form field -- so naming a second tenant
    anywhere in the payload must change nothing about where the rows land.
    """
    target = await make_workspace(db_session, slug="chronon")
    bystander = await make_workspace(db_session, slug="acme")
    await db_session.commit()

    response = await client.post(
        "/api/public/chronon/tickets",
        data=_form(subject="acme", name="acme", company=""),
        headers={"x-relaydesk-workspace": "acme"},
    )
    assert response.status_code == 201

    landed = (await db_session.scalars(sa.select(Conversation))).all()
    assert [conversation.workspace_id for conversation in landed] == [target.id]

    intruders = await db_session.scalar(
        sa.select(sa.func.count())
        .select_from(Conversation)
        .where(Conversation.workspace_id == bystander.id)
    )
    assert intruders == 0


async def test_a_client_supplied_forwarded_header_cannot_change_the_bucket(
    db_session: AsyncSession, client, monkeypatch
) -> None:
    """Route-level, not a unit test of `client_ip.resolve`.

    A client picking its own rate-limit bucket per request was one of this
    slice's two Criticals, and until now the only thing proving it fixed
    was a unit test on the resolver with a mocked request. That would still
    pass if the route stopped consulting the resolver at all. This drives
    the real endpoint: six calls, every one of them claiming a different
    address, and the sixth must still be refused.
    """
    monkeypatch.setattr(get_settings(), "trusted_proxy_ips", "")
    await make_workspace(db_session, slug="chronon")
    await db_session.commit()

    for index in range(5):
        ok = await client.post(
            "/api/public/chronon/tickets",
            data=_form(email=f"ada{index}@example.dev"),
            headers={"x-forwarded-for": f"198.51.100.{index}"},
        )
        assert ok.status_code == 201

    refused = await client.post(
        "/api/public/chronon/tickets",
        data=_form(email="ada5@example.dev"),
        headers={"x-forwarded-for": "198.51.100.99"},
    )

    assert refused.status_code == 429
    keys = set(
        (
            await db_session.scalars(
                sa.select(RateLimitHit.key).where(RateLimitHit.bucket == "tickets")
            )
        ).all()
    )
    assert len(keys) == 1, f"the caller minted its own buckets: {keys}"


async def test_attachments_share_one_budget_and_nothing_is_dropped_silently(
    db_session: AsyncSession, client, monkeypatch
) -> None:
    """The router and `attachments.store` must spend the cap the same way.

    `store` treats `attachment_max_bytes` as one budget across all parts
    and skips whatever no longer fits. While the router checked each file
    against that same number individually, five files just under it all
    passed the router, store kept the ones that fitted and dropped the
    rest, and the submitter was told the ticket was received. The whole
    submission is refused instead, so a dropped attachment is impossible.
    """
    monkeypatch.setattr(get_settings(), "attachment_max_bytes", 1000)
    await make_workspace(db_session, slug="chronon")
    await db_session.commit()

    # Each part is comfortably under the cap on its own; together they are
    # over it. This is the exact shape that used to half-succeed.
    files = [
        ("files", (f"shot{index}.png", b"\x89PNG\r\n\x1a\n" + b"0" * 400, "image/png"))
        for index in range(3)
    ]

    response = await client.post(
        "/api/public/chronon/tickets", data=_form(), files=files
    )

    assert response.status_code == 422
    written = await db_session.scalar(
        sa.select(sa.func.count()).select_from(Conversation)
    )
    assert written == 0


async def test_attachments_inside_the_shared_budget_are_all_stored(
    db_session: AsyncSession, client, monkeypatch
) -> None:
    """The other half of the same contract: within budget, nothing is lost."""
    monkeypatch.setattr(get_settings(), "attachment_max_bytes", 10_000)
    await make_workspace(db_session, slug="chronon")
    await db_session.commit()

    files = [
        ("files", (f"shot{index}.png", b"\x89PNG\r\n\x1a\n" + b"0" * 400, "image/png"))
        for index in range(3)
    ]

    response = await client.post(
        "/api/public/chronon/tickets", data=_form(), files=files
    )

    assert response.status_code == 201
    stored = await db_session.scalar(
        sa.select(sa.func.count()).select_from(Attachment)
    )
    assert stored == 3


async def test_an_oversized_body_is_refused_before_the_limiter_runs(
    db_session: AsyncSession, client
) -> None:
    """Route-level proof of the ordering the body-size middleware exists for.

    This route declares `Form`/`File` parameters, so Starlette parses and
    spools the whole multipart body while resolving the route's
    dependencies -- before the function body, and so before
    `ratelimit.check` inside it, ever runs. An anonymous caller already
    over its cap could still make the process read an unbounded body on
    every attempt, and there is no ingress limit in front of this service.
    The empty `rate_limit_hits` table is what shows the refusal landed
    ahead of the limiter rather than merely instead of it.
    """
    await make_workspace(db_session, slug="chronon")
    await db_session.commit()

    response = await client.post(
        "/api/public/chronon/tickets",
        data=_form(),
        headers={"content-length": str(get_settings().max_request_bytes + 1)},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "too_large"
    charged = await db_session.scalar(
        sa.select(sa.func.count()).select_from(RateLimitHit)
    )
    assert charged == 0
    written = await db_session.scalar(
        sa.select(sa.func.count()).select_from(Conversation)
    )
    assert written == 0
