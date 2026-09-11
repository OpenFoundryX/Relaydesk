import pytest

from relaydesk.models.ai_config import AiConfig
from relaydesk.services.ai_provider import FakeProvider, ProviderUnavailable, for_config


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
