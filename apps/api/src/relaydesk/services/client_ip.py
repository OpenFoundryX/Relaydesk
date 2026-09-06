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


def resolve(request: Request) -> str:
    """The caller's address, as far as it can be trusted.

    ``X-Forwarded-For`` is honoured only when the immediate peer is a proxy
    we configured. Anyone can send the header; only a hop we put there can
    make us believe it.
    """
    peer = request.client.host if request.client else None
    if peer is None:
        return UNKNOWN
    if peer not in _trusted():
        return peer

    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()
    return _valid(first) or peer
