from unittest.mock import Mock

from relaydesk.services import client_ip


def _request(peer: str, forwarded: str | None = None) -> Mock:
    request = Mock()
    request.client = Mock(host=peer)
    request.headers = {"x-forwarded-for": forwarded} if forwarded else {}
    return request


def test_the_peer_address_is_used_when_no_proxy_is_trusted(monkeypatch) -> None:
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "")
    client_ip.get_settings.cache_clear()
    assert client_ip.resolve(_request("203.0.113.9")) == "203.0.113.9"


def test_a_forwarded_header_from_an_untrusted_peer_is_ignored(monkeypatch) -> None:
    """The whole point. A caller reaching the API directly must not be able
    to choose its own rate-limit bucket by sending a header."""
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "10.0.0.5")
    client_ip.get_settings.cache_clear()
    request = _request("203.0.113.9", forwarded="198.51.100.1")
    assert client_ip.resolve(request) == "203.0.113.9"


def test_a_forwarded_header_from_a_trusted_peer_is_honoured(monkeypatch) -> None:
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "10.0.0.5")
    client_ip.get_settings.cache_clear()
    request = _request("10.0.0.5", forwarded="198.51.100.1")
    assert client_ip.resolve(request) == "198.51.100.1"


def test_the_left_most_forwarded_address_wins(monkeypatch) -> None:
    """X-Forwarded-For appends, so the client is left-most and every entry
    to its right was added by a hop closer to us."""
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "10.0.0.5")
    client_ip.get_settings.cache_clear()
    request = _request("10.0.0.5", forwarded="198.51.100.1, 10.0.0.5")
    assert client_ip.resolve(request) == "198.51.100.1"


def test_a_malformed_forwarded_header_falls_back_to_the_peer(monkeypatch) -> None:
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "10.0.0.5")
    client_ip.get_settings.cache_clear()
    request = _request("10.0.0.5", forwarded="not-an-address")
    assert client_ip.resolve(request) == "10.0.0.5"


def test_a_missing_peer_yields_a_stable_placeholder(monkeypatch) -> None:
    """Starlette leaves request.client None for some transports. The limiter
    still needs a key, and every such caller sharing one bucket is the safe
    direction."""
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "")
    client_ip.get_settings.cache_clear()
    request = Mock()
    request.client = None
    request.headers = {}
    assert client_ip.resolve(request) == "unknown"
