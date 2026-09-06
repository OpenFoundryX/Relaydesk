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


def test_an_ipv4_caller_keeps_its_whole_address(monkeypatch) -> None:
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "")
    client_ip.get_settings.cache_clear()
    assert client_ip.resolve(_request("203.0.113.9")) == "203.0.113.9"


def test_an_ipv6_caller_is_bucketed_on_its_64_prefix(monkeypatch) -> None:
    """A residential IPv6 subscriber is handed a /64, not an address.

    Keying on the exact address would give one ordinary broadband line
    2**64 buckets, each with a full allowance, at no cost to it -- which is
    the same as having no limit at all. /64 is the routing boundary, so a
    caller cannot get below it.
    """
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "")
    client_ip.get_settings.cache_clear()
    assert (
        client_ip.resolve(_request("2001:db8:1:2:3:4:5:6")) == "2001:db8:1:2::/64"
    )


def test_two_addresses_in_one_ipv6_64_share_a_bucket(monkeypatch) -> None:
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "")
    client_ip.get_settings.cache_clear()
    first = client_ip.resolve(_request("2001:db8:1:2::1"))
    second = client_ip.resolve(_request("2001:db8:1:2:ffff:ffff:ffff:ffff"))
    assert first == second


def test_two_different_ipv6_64s_do_not_share_a_bucket(monkeypatch) -> None:
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "")
    client_ip.get_settings.cache_clear()
    first = client_ip.resolve(_request("2001:db8:1:2::1"))
    second = client_ip.resolve(_request("2001:db8:1:3::1"))
    assert first != second


def test_a_forwarded_ipv6_address_is_bucketed_the_same_way(monkeypatch) -> None:
    """The prefix rule has to hold on the path a real deployment uses --
    the address arrives through a trusted proxy's header, not the socket."""
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "10.0.0.5")
    client_ip.get_settings.cache_clear()
    request = _request("10.0.0.5", forwarded="2001:db8:1:2:3:4:5:6")
    assert client_ip.resolve(request) == "2001:db8:1:2::/64"


def test_an_ipv6_bucket_fits_the_rate_limit_key_column() -> None:
    """`rate_limit_hits.key` is 64 characters and `ratelimit.check`
    truncates to it. A bucket longer than that would be silently cut, which
    is how a key stops matching its own stored rows."""
    longest = client_ip.bucket("2001:0db8:85a3:0000:ffff:ffff:ffff:ffff")
    assert len(longest) <= 64


def test_the_unknown_placeholder_is_left_alone(monkeypatch) -> None:
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "")
    client_ip.get_settings.cache_clear()
    assert client_ip.bucket(client_ip.UNKNOWN) == client_ip.UNKNOWN
