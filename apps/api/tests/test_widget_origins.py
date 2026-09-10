import pytest

from relaydesk.services import widget_origins as origins


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://acme.com", "https://acme.com"),
        # A trailing slash is what an admin pastes out of a browser bar.
        ("https://acme.com/", "https://acme.com"),
        ("HTTPS://ACME.COM", "https://acme.com"),
        # Default ports are implicit in an Origin header, so storing them
        # explicitly would never match what the browser sends.
        ("https://acme.com:443", "https://acme.com"),
        ("http://acme.com:80", "http://acme.com"),
        ("http://localhost:3000", "http://localhost:3000"),
        ("https://acme.com:8443", "https://acme.com:8443"),
    ],
)
def test_normalise_accepts(raw, expected):
    assert origins.normalise(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "acme.com",                    # no scheme
        "ftp://acme.com",              # not http(s)
        "https://*.acme.com",          # wildcards are refused, spec section 4
        "https://acme.com/help",       # a path is not an origin
        "https://acme.com?x=1",
        "https://acme.com#a",
        "null",                        # a sandboxed iframe's Origin
        "https://",
    ],
)
def test_normalise_rejects(raw):
    assert origins.normalise(raw) is None


def test_empty_allowlist_refuses():
    """Unconfigured means refuse. Permitting here would open every new key."""
    assert origins.allowed([], "https://acme.com") is False


def test_allowed_matches_exactly():
    stored = ["https://acme.com", "https://www.acme.com"]
    assert origins.allowed(stored, "https://acme.com") is True
    assert origins.allowed(stored, "https://acme.com:443") is True
    assert origins.allowed(stored, "https://ACME.com/") is True
    # A subdomain is not the same origin, and neither is another scheme.
    assert origins.allowed(stored, "https://evil.acme.com") is False
    assert origins.allowed(stored, "http://acme.com") is False
    assert origins.allowed(stored, "https://acme.com.evil.com") is False


@pytest.mark.parametrize(
    ("raw", "host"),
    [
        # A userinfo prefix names a login, not a destination -- the host
        # after "@" is what a browser (and urlsplit) actually navigates to.
        # An admin pasting what looks like "acme.com" here must not
        # accidentally allow evil.com.
        ("https://acme.com@evil.com", "evil.com"),
        ("https://acme.com:443@evil.com", "evil.com"),
    ],
)
def test_a_userinfo_prefix_normalises_to_the_host_after_the_at_sign(raw, host):
    assert origins.normalise(raw) == f"https://{host}"
    assert origins.allowed(["https://acme.com"], raw) is False


def test_allowed_refuses_absent_and_opaque_origins():
    stored = ["https://acme.com"]
    assert origins.allowed(stored, None) is False
    assert origins.allowed(stored, "null") is False


def test_frame_ancestors_none_when_unconfigured():
    assert origins.frame_ancestors([]) == "frame-ancestors 'none'"


def test_frame_ancestors_lists_origins():
    header = origins.frame_ancestors(["https://acme.com", "https://www.acme.com"])
    assert header == "frame-ancestors https://acme.com https://www.acme.com"
