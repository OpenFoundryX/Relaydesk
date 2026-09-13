from types import SimpleNamespace

import anthropic
import httpx
import pytest

from relaydesk.models.ai_config import AiConfig
from relaydesk.services.ai_provider import (
    AnthropicProvider,
    FakeProvider,
    ProviderRefused,
    ProviderRejectedRequest,
    ProviderUnavailable,
    Turn,
    for_config,
)


async def test_fake_streams_its_script():
    provider = FakeProvider(chunks=["You can ", "ask for one [1]."])
    received = [chunk async for chunk in provider.complete(
        system="s", question="q", model="claude-opus-5"
    )]
    assert "".join(received) == "You can ask for one [1]."
    assert provider.usage().output_tokens > 0


async def test_fake_can_be_scripted_to_fail():
    """Every caller must have a way to exercise the provider-down path."""
    provider = FakeProvider(fails=True)
    with pytest.raises(ProviderUnavailable):
        [chunk async for chunk in provider.complete(
            system="s", question="q", model="claude-opus-5"
        )]


async def test_fake_usage_does_not_accumulate_across_calls():
    """A shared fixture reused across two calls must not report nonsense."""
    provider = FakeProvider(chunks=["You can ", "ask for one [1]."])
    [chunk async for chunk in provider.complete(
        system="s", question="q", model="claude-opus-5"
    )]
    [chunk async for chunk in provider.complete(
        system="s", question="q", model="claude-opus-5"
    )]
    second_call_usage = provider.usage()

    fresh = FakeProvider(chunks=["You can ", "ask for one [1]."])
    [chunk async for chunk in fresh.complete(
        system="s", question="q", model="claude-opus-5"
    )]
    single_call_usage = fresh.usage()

    assert second_call_usage == single_call_usage


def test_provider_unavailable_hides_the_cause_in_its_message():
    """A visitor must not be able to tell an outage from a refusal.

    The type is already the same either way -- this checks the message is
    too, since the message is what a naive caller is most likely to surface.
    """
    refusal = ProviderUnavailable("refused")
    connection_failure = ProviderUnavailable("Connection reset by peer")
    assert str(refusal) == str(connection_failure)


async def test_fake_can_be_scripted_to_refuse():
    """A caller must have a way to exercise the refusal path, distinctly."""
    provider = FakeProvider(refuses=True)
    with pytest.raises(ProviderRefused):
        [chunk async for chunk in provider.complete(
            system="s", question="q", model="claude-opus-5"
        )]


def test_provider_refused_is_a_provider_unavailable():
    """I1: the visitor-facing degrade path must not need to change.

    A caller that only catches `ProviderUnavailable` -- the type spec D4's
    single degrade path is built on -- must still catch a refusal, so
    `ProviderRefused` has to be a subclass, not a sibling.
    """
    assert issubclass(ProviderRefused, ProviderUnavailable)


def test_provider_refused_hides_the_cause_in_its_message_too():
    """The visitor-facing uniform message (I1's other half) must survive
    the type split: a caller inspecting only `str(exc)` still cannot tell
    a refusal from an outage."""
    refusal = ProviderRefused("refused")
    outage = ProviderUnavailable("Connection reset by peer")
    assert str(refusal) == str(outage)


async def test_fake_records_what_it_was_given():
    """D6's caller-level guarantee needs a fake that can prove what crossed
    the boundary -- see I3/test_ai_answers.py for the caller-level test
    this exists for."""
    provider = FakeProvider(chunks=["ok"])
    [chunk async for chunk in provider.complete(
        system="sys-prompt", question="a@b.com wants a refund", model="claude-opus-5"
    )]
    assert provider.received_system == "sys-prompt"
    assert provider.received_question == "a@b.com wants a refund"


async def test_fake_records_the_history_it_was_given():
    """`FakeProvider` must let a caller assert on prior turns too, not only
    on `system`/`question` -- Change 1's whole reason for existing."""
    provider = FakeProvider(chunks=["ok"])
    history = [Turn(role="visitor", text="how do refunds work")]
    [chunk async for chunk in provider.complete(
        system="s", question="q", model="claude-opus-5", history=history
    )]
    assert provider.received_history == history


async def test_fake_defaults_to_no_history():
    """`None` and `[]` mean the same thing -- a caller that never scripts
    `history` must see an empty list, not `None`, so it need not special-case
    the absence of the argument it did not pass."""
    provider = FakeProvider(chunks=["ok"])
    [chunk async for chunk in provider.complete(
        system="s", question="q", model="claude-opus-5"
    )]
    assert provider.received_history == []


def test_no_key_means_no_provider():
    """`enabled=True` is load-bearing, not decoration.

    `AiConfig.enabled` carries a SQLAlchemy column `default=False`, which is
    applied at INSERT, not at construction: an unflushed `AiConfig()` has
    `enabled is None`. Leave it unset and `for_config` returns `None` on the
    enabled check having never looked at the key, so this test would pass
    unchanged with a real key in place -- naming a guarantee it does not
    observe. Setting it true makes the missing key the only reason.
    """
    config = AiConfig(
        provider="anthropic", model="claude-opus-5", api_key=None, enabled=True
    )
    assert for_config(config) is None


def test_a_configured_workspace_gets_a_provider():
    """The other half: without this, `for_config` returning None always would pass."""
    config = AiConfig(
        provider="anthropic", model="claude-opus-5", api_key="sk-test", enabled=True
    )
    assert for_config(config) is not None


def test_disabled_beats_a_present_key():
    """Switching the feature off must not require discarding the key."""
    config = AiConfig(
        provider="anthropic", model="claude-opus-5", api_key="sk-test", enabled=False
    )
    assert for_config(config) is None


async def test_the_real_provider_raises_refused_not_unavailable_on_a_refusal() -> None:
    """The distinction has to hold in the line that actually runs.

    Every other test of this behaviour drives `FakeProvider`, so reverting
    `AnthropicProvider`'s `ProviderRefused` to `ProviderUnavailable` -- the
    literal defect, in the only line production reaches -- passed the whole
    suite. A guarantee proven only against a test double is a guarantee
    about the test double.

    No network: the client's `messages.stream` is replaced with a context
    manager that yields one chunk and reports a refusal at the end, which
    is the shape the SDK produces.
    """

    class _FinalMessage:
        stop_reason = "refusal"
        usage = SimpleNamespace(input_tokens=11, output_tokens=0)

    class _Stream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        @property
        async def text_stream(self):  # pragma: no cover - replaced below
            raise AssertionError("unused")

        async def get_final_message(self):
            return _FinalMessage()

    async def _chunks():
        yield "I am not able to help with that."

    stream = _Stream()
    type(stream).text_stream = property(lambda self: _chunks())

    provider = AnthropicProvider(api_key="sk-test")
    provider._client = SimpleNamespace(
        messages=SimpleNamespace(stream=lambda **kwargs: stream)
    )

    with pytest.raises(ProviderRefused):
        [chunk async for chunk in provider.complete(
            system="s", question="q", model="claude-opus-5"
        )]


async def test_cached_input_tokens_count_towards_the_budget() -> None:
    """The context is the expensive part, and caching hides it.

    The system block carries `cache_control`, so on a cache hit the SDK
    reports the system prompt and the retrieved articles under
    `cache_read_input_tokens` and leaves `input_tokens` holding little more
    than the question. A real answer over five articles recorded TEN input
    tokens against a daily ceiling that sums this column.

    Cached tokens are cheaper, not free, and the ceiling counts tokens
    rather than money.
    """

    class _FinalMessage:
        stop_reason = "end_turn"
        usage = SimpleNamespace(
            input_tokens=10,
            output_tokens=138,
            cache_read_input_tokens=2400,
            cache_creation_input_tokens=600,
        )

    class _Stream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get_final_message(self):
            return _FinalMessage()

    async def _chunks():
        yield "Within 14 days [1]."

    stream = _Stream()
    type(stream).text_stream = property(lambda self: _chunks())

    provider = AnthropicProvider(api_key="sk-test")
    provider._client = SimpleNamespace(
        messages=SimpleNamespace(stream=lambda **kwargs: stream)
    )

    [chunk async for chunk in provider.complete(
        system="s", question="q", model="claude-opus-5"
    )]

    assert provider.usage().input_tokens == 3010, "cached context must be counted"
    assert provider.usage().output_tokens == 138


async def test_the_real_provider_sends_history_as_prior_messages_not_the_system_prompt() -> (
    None
):
    """Change 1's actual requirement, in the only line production reaches.

    `history` becomes real messages ahead of `question`, oldest first --
    `"visitor"` maps to Anthropic's `"user"`, `"assistant"` passes straight
    through -- rather than being folded into `system`.
    """

    class _FinalMessage:
        stop_reason = "end_turn"
        usage = SimpleNamespace(input_tokens=5, output_tokens=5)

    class _Stream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get_final_message(self):
            return _FinalMessage()

    async def _chunks():
        yield "Same policy [1]."

    stream = _Stream()
    type(stream).text_stream = property(lambda self: _chunks())

    captured: dict = {}

    def _capture(**kwargs):
        captured.update(kwargs)
        return stream

    provider = AnthropicProvider(api_key="sk-test")
    provider._client = SimpleNamespace(messages=SimpleNamespace(stream=_capture))

    [chunk async for chunk in provider.complete(
        system="s",
        question="what about annually?",
        model="claude-opus-5",
        history=[
            Turn(role="visitor", text="how do refunds work"),
            Turn(role="assistant", text="Within 14 days."),
        ],
    )]

    assert captured["messages"] == [
        {"role": "user", "content": "how do refunds work"},
        {"role": "assistant", "content": "Within 14 days."},
        {"role": "user", "content": "what about annually?"},
    ]


async def test_the_real_provider_with_no_history_sends_only_the_question() -> None:
    """The ordinary, first-question-of-a-conversation shape must still work."""

    class _FinalMessage:
        stop_reason = "end_turn"
        usage = SimpleNamespace(input_tokens=5, output_tokens=5)

    class _Stream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get_final_message(self):
            return _FinalMessage()

    async def _chunks():
        yield "Within 14 days [1]."

    stream = _Stream()
    type(stream).text_stream = property(lambda self: _chunks())

    captured: dict = {}

    def _capture(**kwargs):
        captured.update(kwargs)
        return stream

    provider = AnthropicProvider(api_key="sk-test")
    provider._client = SimpleNamespace(messages=SimpleNamespace(stream=_capture))

    [chunk async for chunk in provider.complete(
        system="s", question="refund", model="claude-opus-5"
    )]

    assert captured["messages"] == [{"role": "user", "content": "refund"}]


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (400, ProviderRejectedRequest),
        (401, ProviderRejectedRequest),
        (404, ProviderRejectedRequest),
        (422, ProviderRejectedRequest),
        # Being rate-limited is the provider saying it cannot serve us, not
        # us sending something wrong -- the one 4xx the breaker should see.
        (429, ProviderUnavailable),
        (500, ProviderUnavailable),
        (529, ProviderUnavailable),
    ],
)
async def test_a_rejected_request_is_not_an_outage(status, expected) -> None:
    """A 4xx must not look like the provider being down.

    `breaker_open` counts `provider_unavailable` and nothing else, so
    before this split five malformed requests -- far under any rate limit
    on an anonymous route whose key sits in a page source -- disabled AI
    for a whole workspace for fifteen minutes. The distinction has to live
    in `AnthropicProvider`, the line production actually reaches.
    """

    class _Stream:
        async def __aenter__(self):
            raise anthropic.APIStatusError(
                "boom",
                response=httpx.Response(
                    status, request=httpx.Request("POST", "https://api.anthropic.com")
                ),
                body=None,
            )

        async def __aexit__(self, *exc):
            return False

    provider = AnthropicProvider(api_key="sk-test")
    provider._client = SimpleNamespace(
        messages=SimpleNamespace(stream=lambda **kwargs: _Stream())
    )

    with pytest.raises(expected) as caught:
        async for _ in provider.complete(system="s", question="q", model="m"):
            pass

    # Either way the visitor is told the same thing -- the split is for the
    # audit row and the breaker, never for the person asking.
    assert str(caught.value) == "the model is unavailable"
    if expected is ProviderUnavailable:
        assert not isinstance(caught.value, ProviderRejectedRequest)
