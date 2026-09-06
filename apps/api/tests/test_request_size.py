from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from relaydesk.config import get_settings
from relaydesk.main import app as real_app
from relaydesk.middleware import MaxBodySizeMiddleware


def _probe_app(max_bytes: int) -> tuple[FastAPI, list[int]]:
    """A tiny app whose route records how many bytes it was asked to read.

    The list stays empty when the middleware answered first, which is the
    property under test: not merely that an oversize request is refused,
    but that it is refused *without the body being read*.
    """
    seen: list[int] = []
    probe = FastAPI()
    probe.add_middleware(MaxBodySizeMiddleware, max_bytes=max_bytes)

    @probe.post("/echo")
    async def echo(request: Request) -> dict[str, int]:
        body = await request.body()
        seen.append(len(body))
        return {"read": len(body)}

    return probe, seen


def test_a_body_over_the_cap_is_refused_without_being_read() -> None:
    probe, seen = _probe_app(max_bytes=32)

    with TestClient(probe) as client:
        response = client.post("/echo", content=b"x" * 200)

    assert response.status_code == 413
    assert seen == []


def test_the_refusal_uses_the_standard_error_envelope() -> None:
    """The web client parses `body.error.code`; a middleware that answered
    with anything else would be unreadable to it."""
    probe, _ = _probe_app(max_bytes=32)

    with TestClient(probe) as client:
        response = client.post("/echo", content=b"x" * 200)

    assert response.json() == {
        "error": {"code": "too_large", "message": "That request is too large."}
    }


def test_a_body_within_the_cap_reaches_the_route_untouched() -> None:
    probe, seen = _probe_app(max_bytes=1024)

    with TestClient(probe) as client:
        response = client.post("/echo", content=b"x" * 200)

    assert response.status_code == 200
    assert seen == [200]


def test_a_request_with_no_body_is_left_alone() -> None:
    probe, seen = _probe_app(max_bytes=1)

    with TestClient(probe) as client:
        response = client.get("/does-not-exist")

    assert response.status_code == 404
    assert seen == []


def test_the_declared_length_is_what_decides() -> None:
    """Deciding from Content-Length is the whole point -- reading the body
    to measure it is the cost being avoided. A forged large declaration is
    therefore refused on its own, before a byte is read."""
    probe, seen = _probe_app(max_bytes=32)

    with TestClient(probe) as client:
        response = client.post(
            "/echo", content=b"x", headers={"content-length": "9999999"}
        )

    assert response.status_code == 413
    assert seen == []


def test_the_real_app_applies_the_cap_from_settings() -> None:
    """A middleware class nothing installs protects nothing. The public
    ticket route declares Form/File parameters, so Starlette parses and
    spools the entire multipart body while resolving its dependencies --
    before the route body, and so before the IP rate limiter inside it, has
    run at all. This is what stops an already-refused caller from making
    the process do that work on every attempt.
    """
    installed = [
        middleware
        for middleware in real_app.user_middleware
        if middleware.cls is MaxBodySizeMiddleware
    ]

    assert len(installed) == 1
    assert installed[0].kwargs["max_bytes"] == get_settings().max_request_bytes


def test_the_configured_cap_clears_a_legitimate_submission() -> None:
    """The cap has to sit above anything a real customer can send: the
    whole attachment budget, a full-length message, and multipart framing.
    Set too low, this middleware becomes an outage for the feature it is
    protecting."""
    settings = get_settings()

    largest_honest_submission = (
        settings.attachment_max_bytes
        + settings.ticket_message_max_chars
        # Generous room for the multipart framing around six parts.
        + 8192
    )

    assert settings.max_request_bytes > largest_honest_submission
