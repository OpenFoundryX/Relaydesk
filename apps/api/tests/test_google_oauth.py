import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.config import get_settings
from relaydesk.errors import Unauthorized
from relaydesk.models import (
    Membership,
    MembershipStatus,
    Role,
    User,
    UserIdentity,
    Workspace,
)
from relaydesk.security import oauth_google
from relaydesk.security.oauth_google import (
    GoogleProfile,
    authorization_url,
    exchange_code,
)
from relaydesk.services import auth

_RealAsyncClient = httpx.AsyncClient


def _mock_async_client(handler):
    """Swap ``httpx.AsyncClient`` for one whose transport never leaves the
    process, so ``exchange_code``'s HTTP calls can be driven from a test
    without a real network hop to Google.

    Captures the real class before any test monkeypatches
    ``oauth_google.httpx.AsyncClient`` -- that patch lands on the shared
    ``httpx`` module object, so calling ``httpx.AsyncClient(...)`` from
    inside the factory itself would recurse into the patched version.
    """

    def factory(*args: object, **kwargs: object) -> httpx.AsyncClient:
        return _RealAsyncClient(transport=httpx.MockTransport(handler))

    return factory


async def seed_member(session: AsyncSession, email: str) -> User:
    workspace = Workspace(name="Chronon", slug="chronon", monogram="CH")
    user = User(email=email, name="Nilesh Pant", monogram="NP")
    session.add_all([workspace, user])
    await session.flush()
    session.add(
        Membership(
            workspace_id=workspace.id,
            user_id=user.id,
            role=Role.admin,
            status=MembershipStatus.active,
        )
    )
    await session.commit()
    return user


async def test_google_login_links_an_existing_member(db_session: AsyncSession) -> None:
    user = await seed_member(db_session, "nilesh@relaydesk.dev")
    profile = GoogleProfile(
        sub="google-123",
        email="nilesh@relaydesk.dev",
        name="Nilesh Pant",
        email_verified=True,
    )

    result = await auth.login_with_google(db_session, profile)

    assert result.id == user.id
    identity = await db_session.scalar(
        UserIdentity.__table__.select().where(
            UserIdentity.provider_account_id == "google-123"
        )
    )
    assert identity is not None


async def test_google_login_is_idempotent(db_session: AsyncSession) -> None:
    await seed_member(db_session, "nilesh@relaydesk.dev")
    profile = GoogleProfile(
        sub="google-123",
        email="nilesh@relaydesk.dev",
        name="Nilesh Pant",
        email_verified=True,
    )

    first = await auth.login_with_google(db_session, profile)
    second = await auth.login_with_google(db_session, profile)

    assert first.id == second.id


async def test_unknown_email_is_rejected(db_session: AsyncSession) -> None:
    profile = GoogleProfile(
        sub="google-999",
        email="stranger@example.com",
        name="Stranger",
        email_verified=True,
    )

    with pytest.raises(Unauthorized):
        await auth.login_with_google(db_session, profile)


async def test_unverified_email_is_rejected(db_session: AsyncSession) -> None:
    await seed_member(db_session, "nilesh@relaydesk.dev")
    profile = GoogleProfile(
        sub="google-123",
        email="nilesh@relaydesk.dev",
        name="Nilesh",
        email_verified=False,
    )

    with pytest.raises(Unauthorized):
        await auth.login_with_google(db_session, profile)


async def test_member_without_active_membership_is_rejected(
    db_session: AsyncSession,
) -> None:
    user = User(email="orphan@relaydesk.dev", name="Orphan", monogram="OR")
    db_session.add(user)
    await db_session.commit()
    profile = GoogleProfile(
        sub="google-777",
        email="orphan@relaydesk.dev",
        name="Orphan",
        email_verified=True,
    )

    with pytest.raises(Unauthorized):
        await auth.login_with_google(db_session, profile)


async def test_google_login_rejects_a_sub_linked_to_a_different_user(
    db_session: AsyncSession,
) -> None:
    """The (provider, provider_account_id) constraint means a Google sub is
    linked to exactly one user; if that user isn't the one this email just
    resolved to, something is wrong and the login must be refused rather
    than silently proceeding as the email-resolved user.
    """
    await seed_member(db_session, "nilesh@relaydesk.dev")
    other_workspace = Workspace(name="Other", slug="other", monogram="OT")
    other_user = User(email="other@relaydesk.dev", name="Other", monogram="OT")
    db_session.add_all([other_workspace, other_user])
    await db_session.flush()
    db_session.add(
        UserIdentity(
            user_id=other_user.id,
            provider="google",
            provider_account_id="google-123",
        )
    )
    await db_session.commit()

    profile = GoogleProfile(
        sub="google-123",
        email="nilesh@relaydesk.dev",
        name="Nilesh Pant",
        email_verified=True,
    )

    with pytest.raises(Unauthorized):
        await auth.login_with_google(db_session, profile)


def test_authorization_url_raises_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "google_client_id", "")

    with pytest.raises(Unauthorized):
        authorization_url("http://localhost:3000/login/google/callback", "state")


async def test_exchange_code_wraps_a_token_endpoint_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "invalid_grant"})

    monkeypatch.setattr(oauth_google.httpx, "AsyncClient", _mock_async_client(handler))

    with pytest.raises(Unauthorized):
        await exchange_code("bad-code", "http://localhost:3000/login/google/callback")


async def test_exchange_code_rejects_a_token_body_without_an_access_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    monkeypatch.setattr(oauth_google.httpx, "AsyncClient", _mock_async_client(handler))

    with pytest.raises(Unauthorized):
        await exchange_code("code", "http://localhost:3000/login/google/callback")


async def test_exchange_code_wraps_a_userinfo_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "tok"})
        return httpx.Response(500, text="boom")

    monkeypatch.setattr(oauth_google.httpx, "AsyncClient", _mock_async_client(handler))

    with pytest.raises(Unauthorized):
        await exchange_code("code", "http://localhost:3000/login/google/callback")


async def test_exchange_code_wraps_a_transport_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Google being unreachable (timeout, connection refused, ...) must not
    escape as a bare 500 -- there is no generic ``Exception`` handler
    registered, only ``AppError``/validation/HTTP-exception handlers.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    monkeypatch.setattr(oauth_google.httpx, "AsyncClient", _mock_async_client(handler))

    with pytest.raises(Unauthorized):
        await exchange_code("code", "http://localhost:3000/login/google/callback")


async def test_exchange_code_wraps_a_malformed_userinfo_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "tok"})
        return httpx.Response(200, text="not json")

    monkeypatch.setattr(oauth_google.httpx, "AsyncClient", _mock_async_client(handler))

    with pytest.raises(Unauthorized):
        await exchange_code("code", "http://localhost:3000/login/google/callback")


async def test_exchange_code_wraps_a_userinfo_body_missing_sub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "tok"})
        return httpx.Response(200, json={"email": "a@b.com"})

    monkeypatch.setattr(oauth_google.httpx, "AsyncClient", _mock_async_client(handler))

    with pytest.raises(Unauthorized):
        await exchange_code("code", "http://localhost:3000/login/google/callback")


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (True, True),
        (False, False),
        ("true", True),
        ("True", True),
        ("false", False),
        (None, False),
    ],
)
async def test_exchange_code_coerces_email_verified(
    monkeypatch: pytest.MonkeyPatch, raw_value: object, expected: bool
) -> None:
    """Google's ``email_verified`` claim can arrive as a JSON boolean or as
    the string "true"/"false" depending on the endpoint. ``bool("false")``
    is ``True`` in Python -- that would let an unverified address slip past
    the check this value gates, which is exactly the account-takeover
    vector the check exists to stop.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "tok"})
        body = {"sub": "g-1", "email": "a@b.com", "name": "A"}
        if raw_value is not None:
            body["email_verified"] = raw_value
        return httpx.Response(200, json=body)

    monkeypatch.setattr(oauth_google.httpx, "AsyncClient", _mock_async_client(handler))

    profile = await exchange_code("code", "http://localhost:3000/login/google/callback")
    assert profile.email_verified is expected


async def test_google_url_accepts_camel_case_redirect_uri(client: AsyncClient) -> None:
    """Pins the ``Query(alias="redirectUri")`` binding: without it, this
    call 422s before the endpoint's own logic runs, since a plain
    ``redirect_uri: str`` parameter binds to the snake_case query key only.
    """
    response = await client.get(
        "/api/auth/google/url", params={"redirectUri": "http://localhost:3000/x"}
    )
    assert response.status_code != 422
