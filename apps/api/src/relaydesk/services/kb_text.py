"""Text transforms for the knowledge base. Pure -- no database, no settings.

``extract_text`` is what feeds Postgres full-text search today and what slice
4 will retrieve against for AI grounding, so it is kept free of I/O and
tolerant of anything the editor posts: an unknown node type is walked
through rather than tripped over, and a malformed document yields an empty
string rather than raising into a save the author cannot diagnose.
"""

import re
import unicodedata

SLUG_MAX_LENGTH = 200
SLUG_FALLBACK = "untitled"

_WHITESPACE = re.compile(r"\s+")
_JOIN_CHARS = re.compile(r"['\"‘’“”]")
_NON_SLUG = re.compile(r"[^a-z0-9-]+")


def extract_text(doc: object) -> str:
    """Concatenate every text node in document order."""
    parts: list[str] = []
    _walk(doc, parts)
    return _WHITESPACE.sub(" ", " ".join(parts)).strip()


def _walk(node: object, parts: list[str]) -> None:
    if not isinstance(node, dict):
        return

    text = node.get("text")
    if isinstance(text, str):
        parts.append(text)

    content = node.get("content")
    if isinstance(content, list):
        for child in content:
            _walk(child, parts)


def slugify(value: str) -> str:
    """A URL-safe, stable identifier. Never empty, always bounded."""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    lowercase = ascii_only.lower()
    # Remove characters that should join adjacent letters
    no_join = _JOIN_CHARS.sub("", lowercase)
    # Replace runs of non-alphanumeric characters (except hyphens) with single hyphen
    slug = _NON_SLUG.sub("-", no_join).strip("-")
    return (slug or SLUG_FALLBACK)[:SLUG_MAX_LENGTH].strip("-") or SLUG_FALLBACK


def derive_excerpt(body_text: str, limit: int = 200) -> str:
    """The fallback shown under a title when nobody wrote one."""
    text = body_text.strip()
    if len(text) <= limit:
        return text
    clipped = text[:limit].rsplit(" ", 1)[0].rstrip(".,;:")
    return f"{clipped}…"
