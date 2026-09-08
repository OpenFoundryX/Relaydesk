"""The URL policy, asserted as a table with no network anywhere near it."""

import pytest

from relaydesk.errors import Invalid
from relaydesk.services import url_guard


@pytest.fixture
def resolve_to(monkeypatch):
    """Pin DNS, so these tests assert the policy rather than the internet."""

    def _set(*addresses: str) -> None:
        monkeypatch.setattr(url_guard, "_resolve", lambda host: list(addresses))

    _set("93.184.216.34")
    return _set


def test_a_public_https_url_is_dispatchable(resolve_to) -> None:
    url_guard.ensure_dispatchable_url("https://api.example.com/relaydesk/refund")


@pytest.mark.parametrize(
    "url",
    [
        "http://api.example.com/hook",
        "ftp://api.example.com/hook",
        "https:///no-host",
        "not a url at all",
        "/relative/path",
    ],
)
def test_only_an_absolute_https_url_is_dispatchable(resolve_to, url: str) -> None:
    with pytest.raises(Invalid):
        url_guard.ensure_dispatchable_url(url)


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.5",
        "172.16.0.1",
        "192.168.1.1",
        # Cloud instance metadata: the address this guard most exists for.
        "169.254.169.254",
        "0.0.0.0",
        "::1",
        "fc00::1",
        "fe80::1",
        "224.0.0.1",
    ],
)
def test_an_address_off_the_public_internet_is_refused(resolve_to, address) -> None:
    resolve_to(address)
    with pytest.raises(Invalid):
        url_guard.ensure_dispatchable_url("https://internal.example.com/hook")


def test_one_private_answer_among_public_ones_refuses_the_url(resolve_to) -> None:
    resolve_to("93.184.216.34", "127.0.0.1")
    with pytest.raises(Invalid):
        url_guard.ensure_dispatchable_url("https://split.example.com/hook")


def test_a_host_that_does_not_resolve_is_refused(resolve_to) -> None:
    resolve_to()
    with pytest.raises(Invalid):
        url_guard.ensure_dispatchable_url("https://nxdomain.example.com/hook")


def test_an_unparseable_resolver_answer_is_refused(resolve_to) -> None:
    resolve_to("not-an-address")
    with pytest.raises(Invalid):
        url_guard.ensure_dispatchable_url("https://odd.example.com/hook")


def test_the_allow_private_flag_admits_a_private_address(
    monkeypatch, resolve_to
) -> None:
    resolve_to("10.0.0.5")
    monkeypatch.setattr(url_guard, "_allow_private", lambda: True)
    url_guard.ensure_dispatchable_url("https://tools.internal/hook")


def test_the_allow_private_flag_does_not_admit_plain_http(monkeypatch) -> None:
    """It relaxes which networks are reachable, not whether the payload is
    sent in clear."""
    monkeypatch.setattr(url_guard, "_allow_private", lambda: True)
    with pytest.raises(Invalid):
        url_guard.ensure_dispatchable_url("http://tools.internal/hook")


def test_the_flag_is_read_from_settings(monkeypatch) -> None:
    """The seam the other tests pin is wired to the real setting."""
    from relaydesk.config import get_settings

    monkeypatch.setattr(get_settings(), "webhook_allow_private", True)
    assert url_guard._allow_private() is True


def test_the_cheap_check_returns_the_hostname_without_resolving() -> None:
    """``ensure_https_url`` is what registration uses, and it touches no
    resolver -- so it must not be the thing that decides reachability."""
    assert url_guard.ensure_https_url("https://api.example.com/hook") == (
        "api.example.com"
    )


def test_the_cheap_check_still_refuses_plain_http() -> None:
    with pytest.raises(Invalid):
        url_guard.ensure_https_url("http://api.example.com/hook")
