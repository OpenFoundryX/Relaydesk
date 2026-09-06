import ipaddress

from fastapi import Request

from relaydesk.config import get_settings

UNKNOWN = "unknown"


def _trusted() -> frozenset[str]:
    raw = get_settings().trusted_proxy_ips
    return frozenset(entry.strip() for entry in raw.split(",") if entry.strip())


def _valid(address: str) -> str | None:
    try:
        return str(ipaddress.ip_address(address))
    except ValueError:
        return None


def bucket(address: str) -> str:
    """The rate-limit key an address belongs to.

    An IPv4 address is its own bucket. An IPv6 address is bucketed on its
    /64 prefix, because that is the smallest allocation a residential
    subscriber is given: keying on the exact address would hand one
    ordinary broadband line 2**64 buckets, each with a full allowance, at
    no cost to it -- which is the same as having no limit at all. /64 is
    the routing boundary, so this cannot be narrowed by the caller.

    Anything that is not an address (the ``unknown`` placeholder) is
    returned unchanged; it is already a single shared bucket.
    """
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return address
    if parsed.version == 6:
        return str(ipaddress.ip_network(f"{parsed}/64", strict=False))
    return str(parsed)


def resolve(request: Request) -> str:
    """The caller's rate-limit bucket, as far as the caller can be trusted.

    ``X-Forwarded-For`` is honoured only when the immediate peer is a proxy
    we configured. Anyone can send the header; only a hop we put there can
    make us believe it.
    """
    peer = request.client.host if request.client else None
    if peer is None:
        return UNKNOWN
    if peer not in _trusted():
        return bucket(peer)

    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()
    return bucket(_valid(first) or peer)
