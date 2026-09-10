"""Which sites may embed a widget, and how that is enforced.

The panel is an iframe served from Relaydesk's own origin, so the embedding
page never makes a cross-origin request and CORS is not involved at all. What
is being controlled is who may *frame* us, which is
``Content-Security-Policy: frame-ancestors``.

Both that and CORS are enforced by the browser and by nothing else -- a
script that is not a browser ignores both. This is abuse control, not
authorization, and it is acceptable only because every endpoint a widget key
reaches is already public (spec D2). Nothing here should ever be relied on to
keep a stranger away from something.

Pure functions: no session, no request, no settings. Everything that decides
whether a frame renders lives here so it can be tested exhaustively.
"""

from urllib.parse import urlsplit

_DEFAULT_PORTS = {"https": 443, "http": 80}


def normalise(value: str) -> str | None:
    """``value`` reduced to ``scheme://host[:port]``, or ``None`` if it is not an origin.

    Rejects wildcards outright. A pattern like ``*.acme.com`` needs a matcher
    rather than a comparison, and a matcher is the thing that goes subtly
    wrong -- ``*.com`` being the memorable version. Spec section 4 keeps v1
    to exact origins for that reason.
    """
    candidate = value.strip().rstrip("/")
    if not candidate or "*" in candidate:
        return None

    parts = urlsplit(candidate)
    if parts.scheme not in _DEFAULT_PORTS:
        return None
    if parts.path or parts.query or parts.fragment:
        return None
    if not parts.hostname:
        return None

    host = parts.hostname.lower()
    try:
        port = parts.port
    except ValueError:
        # A non-numeric port; urlsplit only raises when it is asked.
        return None

    if port is None or port == _DEFAULT_PORTS[parts.scheme]:
        return f"{parts.scheme}://{host}"
    return f"{parts.scheme}://{host}:{port}"


def allowed(origins: list[str], candidate: str | None) -> bool:
    """Whether ``candidate`` is one of ``origins``.

    An empty ``origins`` refuses. A key that has been created but not
    configured is inert, which is the safe direction to fail: the opposite
    would leave every freshly minted key embeddable anywhere until someone
    remembered to restrict it.
    """
    if not origins or candidate is None:
        return False
    normalised = normalise(candidate)
    if normalised is None:
        return False
    return normalised in {stored for stored in map(normalise, origins) if stored}


def frame_ancestors(origins: list[str]) -> str:
    """The CSP header value for a frame response."""
    permitted = [stored for stored in map(normalise, origins) if stored]
    if not permitted:
        return "frame-ancestors 'none'"
    return "frame-ancestors " + " ".join(permitted)
