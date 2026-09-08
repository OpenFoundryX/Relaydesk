"""Turn a webhook and a dict of arguments into one signed HTTP request.

The module holds no session and imports no FastAPI: it takes a model
instance and returns a value, which is what lets its tests run on
``httpx.MockTransport`` with no database and no socket.

It does not raise for a failing receiver. A refused connection, a timeout, a
500 and a URL the guard rejects are all outcomes of the question the caller
asked -- "what happens when we call this?" -- so they come back as a
``DispatchResult`` with ``ok=False``. Bad *arguments* are different: they are
the caller's own mistake, so they raise ``Invalid`` and become a 422 rather
than a report that the call failed.
"""

import hashlib
import hmac
import json
import time
from dataclasses import dataclass

import httpx

from relaydesk.config import get_settings
from relaydesk.errors import Invalid
from relaydesk.models import Webhook
from relaydesk.services.url_guard import ensure_dispatchable_url

# Read at most this much of a response, and keep at most this much of what we
# read. A receiver does not get to decide how much memory the API spends, and
# nothing downstream needs more than the first few kilobytes to show an admin
# what came back.
READ_LIMIT = 64 * 1024
BODY_LIMIT = 4 * 1024

# Methods that carry their arguments in the query string rather than a body.
QUERY_METHODS = frozenset({"GET", "DELETE"})


@dataclass(frozen=True)
class DispatchResult:
    """What came back, whether or not anything came back."""

    ok: bool
    status: int | None
    duration_ms: int
    response_body: str
    error: str | None


def sign(secret: str, timestamp: int, method: str, url: str, body: str) -> str:
    """The hex HMAC-SHA256 a receiver recomputes to verify a request.

    The signed payload is ``{timestamp}.{method}.{url}.{body}``, and the URL
    is the fully-built one, query string included.

    Stripe's better-known scheme signs ``{timestamp}.{body}`` and was
    rejected here (spec D4) because half the methods this registry allows
    carry no body: under it, every GET a workspace sent would produce a
    signature equally valid for any other GET to any URL, attesting to a
    timestamp and nothing else.

    ``timestamp`` is there so a receiver can reject replays outside its own
    tolerance window. Relaydesk does not enforce that window -- it cannot;
    only the receiver knows what it will accept -- so a receiver that ignores
    the timestamp has no replay protection at all.
    """
    payload = f"{timestamp}.{method}.{url}.{body}"
    return hmac.new(
        secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()


def _coerce(name: str, declared: str, value: object) -> object:
    """One argument, as the type the webhook declared, or ``Invalid``."""
    if declared == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in {"true", "false"}:
            return value.lower() == "true"
        if value in (0, 1):
            return bool(value)
        raise Invalid(f"{name} must be true or false.")

    if declared == "number":
        # bool is an int in Python, and a webhook that asked for a number
        # meant a number.
        if isinstance(value, bool):
            raise Invalid(f"{name} must be a number.")
        if isinstance(value, int | float):
            number = value
        elif isinstance(value, str):
            try:
                number = float(value)
            except ValueError:
                raise Invalid(f"{name} must be a number.") from None
        else:
            raise Invalid(f"{name} must be a number.")
        # 250.0 goes on the wire as 250: a receiver expecting cents should
        # not have to parse a float it never asked for.
        as_int = int(number)
        return as_int if as_int == number else number

    if isinstance(value, str):
        return value
    if isinstance(value, bool | int | float):
        return str(value)
    raise Invalid(f"{name} must be a string.")


def prepare_arguments(
    webhook: Webhook, arguments: dict[str, object]
) -> dict[str, object]:
    """The arguments this webhook actually accepts, typed as it declared.

    Anything not declared is dropped rather than forwarded. The parameter
    list is the contract, and a caller inventing a field is a caller with a
    bug -- passing it through quietly would make that bug the receiver's
    problem, at the receiver's endpoint, under our signature.
    """
    prepared: dict[str, object] = {}
    for param in webhook.params:
        name = param["name"]
        if name in arguments and arguments[name] is not None:
            prepared[name] = _coerce(name, param.get("type", "string"), arguments[name])
        elif param.get("required"):
            raise Invalid(f"{name} is required.")
    return prepared


async def dispatch(
    webhook: Webhook,
    arguments: dict[str, object],
    *,
    client: httpx.AsyncClient | None = None,
) -> DispatchResult:
    """Call the webhook once, signed, and report what happened.

    One attempt, never retried. This registry's own example tool is
    ``refund_order``, and a retried refund is a second refund; whether a
    given endpoint is idempotent is a per-tool fact nothing in the model
    records, so the honest default is to try once and report the failure
    (spec D7).
    """
    method = str(webhook.method)
    # Raises for bad arguments, before anything is sent. A caller that got
    # the arguments wrong has not made a failed call; it has not made a call.
    prepared = prepare_arguments(webhook, arguments)

    settings = get_settings()
    owned = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=settings.webhook_timeout_seconds)

    started = time.perf_counter()

    def elapsed_ms() -> int:
        return int((time.perf_counter() - started) * 1000)

    try:
        # Re-checked here rather than trusted from registration time: DNS is
        # mutable between saving a URL and calling it (spec D8).
        try:
            ensure_dispatchable_url(webhook.url)
        except Invalid as error:
            return DispatchResult(
                ok=False,
                status=None,
                duration_ms=elapsed_ms(),
                response_body="",
                error=error.message,
            )

        query = prepared if method in QUERY_METHODS else None
        body = "" if method in QUERY_METHODS else json.dumps(prepared)
        headers = {"User-Agent": "Relaydesk-Webhooks/1"}
        if method not in QUERY_METHODS:
            headers["Content-Type"] = "application/json"

        # The body is serialised once and sent as raw content, so the bytes
        # signed are the bytes sent. Handing httpx ``json=`` instead would
        # let it re-serialise, and a signature over a different rendering of
        # the same object is a signature that fails at the receiver.
        request = client.build_request(
            method, webhook.url, params=query, content=body.encode(), headers=headers
        )
        timestamp = int(time.time())
        # Signed after building, so the URL signed is the one sent, query
        # string and all.
        signature = sign(
            webhook.secret, timestamp, method, str(request.url), body
        )
        request.headers["Relaydesk-Signature"] = f"t={timestamp},v1={signature}"
        request.headers["Relaydesk-Webhook-Id"] = str(webhook.id)

        try:
            # Redirects are not followed: a permitted public URL that answers
            # 302 with a location inside the private network is precisely the
            # bypass the guard above exists to prevent, and no tool endpoint
            # needs one.
            response = await client.send(request, follow_redirects=False, stream=True)
        except httpx.HTTPError as error:
            return DispatchResult(
                ok=False,
                status=None,
                duration_ms=elapsed_ms(),
                response_body="",
                error=f"{type(error).__name__}: {error}",
            )

        try:
            chunks: list[bytes] = []
            read = 0
            async for chunk in response.aiter_bytes():
                chunks.append(chunk)
                read += len(chunk)
                if read >= READ_LIMIT:
                    break
        except httpx.HTTPError as error:
            return DispatchResult(
                ok=False,
                status=response.status_code,
                duration_ms=elapsed_ms(),
                response_body="",
                error=f"{type(error).__name__}: {error}",
            )
        finally:
            await response.aclose()

        text = b"".join(chunks).decode("utf-8", "replace")[:BODY_LIMIT]
        return DispatchResult(
            ok=200 <= response.status_code < 300,
            status=response.status_code,
            duration_ms=elapsed_ms(),
            response_body=text,
            error=None,
        )
    finally:
        if owned:
            await client.aclose()
