"""The dispatcher, on a mock transport -- no database, no socket."""

import uuid

import httpx
import pytest

from relaydesk.errors import Invalid
from relaydesk.models import Webhook, WebhookMethod
from relaydesk.services import webhook_dispatch

DEFAULT_PARAMS = [
    {"name": "order_id", "type": "string", "description": "", "required": True},
    {"name": "amount", "type": "number", "description": "", "required": False},
    {"name": "notify", "type": "boolean", "description": "", "required": False},
]


def make_webhook(
    method: WebhookMethod = WebhookMethod.post,
    url: str = "https://api.example.com/relaydesk/refund",
    params: list[dict] | None = None,
) -> Webhook:
    return Webhook(
        id=uuid.uuid4(),
        name="refund_order",
        description="Refunds an order by its order_id.",
        method=method,
        url=url,
        secret="whsec_fixed",
        params=DEFAULT_PARAMS if params is None else params,
    )


def capturing(captured: list, *, status: int = 200, body: str = "ok"):
    def handler(request: httpx.Request) -> httpx.Response:
        request.read()
        captured.append(request)
        return httpx.Response(status, text=body)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def responding(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def signature_parts(request: httpx.Request) -> tuple[int, str]:
    header = request.headers["relaydesk-signature"]
    timestamp, version = header.split(",")
    return int(timestamp.removeprefix("t=")), version.removeprefix("v1=")


@pytest.fixture(autouse=True)
def allow_any_url(monkeypatch):
    """The guard has its own tests; these assert what is sent."""
    monkeypatch.setattr(webhook_dispatch, "ensure_dispatchable_url", lambda url: None)


def test_the_signature_is_a_fixed_vector() -> None:
    """Pinned so that changing the scheme has to be a deliberate act.

    Anything that edits the signed payload breaks this test and every
    receiver in the field at the same time; the test is here so the first
    happens before the second.
    """
    assert webhook_dispatch.sign(
        "whsec_fixed",
        1757376000,
        "POST",
        "https://api.example.com/relaydesk/refund",
        '{"order_id": "A1"}',
    ) == "12156730eb59c98a508afb647d62378061058e7dcf066f7eb9b39c906123f0fc"


async def test_a_post_sends_json_and_signs_exactly_what_it_sent() -> None:
    captured: list[httpx.Request] = []
    result = await webhook_dispatch.dispatch(
        make_webhook(), {"order_id": "A1"}, client=capturing(captured)
    )

    request = captured[0]
    assert result.ok is True and result.status == 200
    assert result.response_body == "ok"
    assert request.headers["content-type"] == "application/json"
    assert request.content == b'{"order_id": "A1"}'

    timestamp, signature = signature_parts(request)
    assert signature == webhook_dispatch.sign(
        "whsec_fixed", timestamp, "POST", str(request.url), request.content.decode()
    )


async def test_the_webhook_id_travels_with_the_request() -> None:
    captured: list[httpx.Request] = []
    hook = make_webhook()
    await webhook_dispatch.dispatch(
        hook, {"order_id": "A1"}, client=capturing(captured)
    )

    assert captured[0].headers["relaydesk-webhook-id"] == str(hook.id)


async def test_a_get_puts_arguments_in_the_query_and_signs_that_url() -> None:
    captured: list[httpx.Request] = []
    hook = make_webhook(
        method=WebhookMethod.get, url="https://api.example.com/subscription"
    )

    await webhook_dispatch.dispatch(
        hook, {"order_id": "A1", "amount": 250}, client=capturing(captured)
    )

    request = captured[0]
    assert request.url.params["order_id"] == "A1"
    assert request.content == b""
    timestamp, signature = signature_parts(request)
    # The signed URL is the built one, so the query string is covered.
    assert "order_id=A1" in str(request.url)
    assert signature == webhook_dispatch.sign(
        "whsec_fixed", timestamp, "GET", str(request.url), ""
    )


async def test_a_missing_required_argument_makes_no_request_at_all() -> None:
    captured: list[httpx.Request] = []
    with pytest.raises(Invalid):
        await webhook_dispatch.dispatch(make_webhook(), {}, client=capturing(captured))

    assert captured == []


async def test_an_undeclared_argument_is_dropped_not_forwarded() -> None:
    captured: list[httpx.Request] = []
    await webhook_dispatch.dispatch(
        make_webhook(),
        {"order_id": "A1", "sneaky": "../../etc/passwd"},
        client=capturing(captured),
    )

    assert b"sneaky" not in captured[0].content


async def test_a_value_that_will_not_coerce_is_refused() -> None:
    with pytest.raises(Invalid):
        await webhook_dispatch.dispatch(
            make_webhook(),
            {"order_id": "A1", "amount": "not a number"},
            client=capturing([]),
        )


async def test_a_numeric_string_arrives_as_a_number() -> None:
    captured: list[httpx.Request] = []
    await webhook_dispatch.dispatch(
        make_webhook(), {"order_id": "A1", "amount": "250"}, client=capturing(captured)
    )

    assert b'"amount": 250' in captured[0].content


async def test_a_boolean_string_arrives_as_a_boolean() -> None:
    captured: list[httpx.Request] = []
    await webhook_dispatch.dispatch(
        make_webhook(),
        {"order_id": "A1", "notify": "false"},
        client=capturing(captured),
    )

    assert b'"notify": false' in captured[0].content


async def test_an_optional_argument_left_out_is_simply_absent() -> None:
    captured: list[httpx.Request] = []
    await webhook_dispatch.dispatch(
        make_webhook(), {"order_id": "A1"}, client=capturing(captured)
    )

    assert captured[0].content == b'{"order_id": "A1"}'


async def test_a_redirect_is_reported_not_followed() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://169.254.169.254/"})

    result = await webhook_dispatch.dispatch(
        make_webhook(), {"order_id": "A1"}, client=responding(handler)
    )

    assert result.ok is False and result.status == 302
    assert seen == ["https://api.example.com/relaydesk/refund"]


async def test_a_failing_receiver_is_a_result_not_an_exception() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    result = await webhook_dispatch.dispatch(
        make_webhook(), {"order_id": "A1"}, client=responding(handler)
    )

    assert result.ok is False and result.status == 500
    assert result.response_body == "boom" and result.error is None


async def test_a_timeout_is_a_result_not_an_exception() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("too slow")

    result = await webhook_dispatch.dispatch(
        make_webhook(), {"order_id": "A1"}, client=responding(handler)
    )

    assert result.ok is False and result.status is None
    assert "ConnectTimeout" in result.error


async def test_a_url_the_guard_refuses_is_a_result_not_an_exception(
    monkeypatch,
) -> None:
    def refuse(url: str) -> None:
        raise Invalid("resolves to an address that is not on the public internet.")

    monkeypatch.setattr(webhook_dispatch, "ensure_dispatchable_url", refuse)

    result = await webhook_dispatch.dispatch(make_webhook(), {"order_id": "A1"})

    assert result.ok is False and result.status is None
    assert "public internet" in result.error


async def test_an_oversized_response_body_is_truncated() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="x" * 200_000)

    result = await webhook_dispatch.dispatch(
        make_webhook(), {"order_id": "A1"}, client=responding(handler)
    )

    assert len(result.response_body) == webhook_dispatch.BODY_LIMIT
