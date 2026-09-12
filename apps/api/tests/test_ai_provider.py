import pytest

from relaydesk.models.ai_config import AiConfig
from relaydesk.services.ai_provider import (
    FakeProvider,
    ProviderRefused,
    ProviderUnavailable,
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
