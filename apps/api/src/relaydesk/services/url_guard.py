"""Whether a workspace-supplied URL may be dispatched to.

Its own module, separate from the dispatcher, because a deny list is exactly
the kind of code that should be testable by a table of addresses with no
server anywhere near it.

The check runs on every dispatch rather than only when a webhook is saved
(spec D8). Registering a URL and calling it are separated in time, and DNS is
mutable in between, so a check performed only at save is a check an attacker
schedules around.

One limitation is carried rather than hidden: the hostname is resolved here
and resolved again by httpx when it connects, so a name that answers publicly
for the first lookup and privately for the second defeats this. Closing that
window needs a transport pinned to the validated address with an explicit
Host header. The residual risk is recorded in section 12 of the design.
"""

import ipaddress
import socket
from urllib.parse import urlsplit

from relaydesk.config import get_settings
from relaydesk.errors import Invalid

# Both are module-level indirections so tests can pin them: one to assert the
# policy without touching DNS, the other without touching the environment.


def _allow_private() -> bool:
    return get_settings().webhook_allow_private


def _resolve(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return []
    return [info[4][0] for info in infos]


def _is_off_limits(address: str) -> bool:
    """True for anything that is not a public internet address.

    ``is_private`` already covers 10/8, 172.16/12, 192.168/16 and fc00::/7;
    the rest are named because they are not private in that sense and are
    each a way out of this check. ``is_link_local`` is the important one: it
    covers 169.254.0.0/16, which is where cloud instance metadata --
    credentials, in practice -- answers.
    """
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        # A resolver that returned something unparseable is not a resolver
        # whose answer should be dialled.
        return True
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def ensure_https_url(url: str) -> str:
    """The hostname, if this is an absolute https URL. Otherwise ``Invalid``.

    The cheap half of the check, split out so that registering a webhook can
    reject a malformed URL without a DNS lookup -- and so that the service
    layer's tests do not need a resolver. It is a convenience, not the
    control: ``ensure_dispatchable_url`` at dispatch time is what actually
    holds the line.
    """
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise Invalid("A webhook URL must be an absolute https:// URL.")
    return parts.hostname


def ensure_dispatchable_url(url: str) -> None:
    """Raise ``Invalid`` unless the server may make a request to this URL."""
    hostname = ensure_https_url(url)

    # The scheme requirement holds even here: this flag is about which
    # networks are reachable, not about sending signed payloads in clear.
    if _allow_private():
        return

    addresses = _resolve(hostname)
    if not addresses:
        raise Invalid(f"{hostname} does not resolve to any address.")
    # Every answer must pass. A host that returns one public address and one
    # loopback address is refused: the connection would pick either.
    if any(_is_off_limits(address) for address in addresses):
        raise Invalid(
            f"{hostname} resolves to an address that is not on the "
            "public internet. Set RELAYDESK_WEBHOOK_ALLOW_PRIVATE=true if "
            "that is deliberate."
        )
