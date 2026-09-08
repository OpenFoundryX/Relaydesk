"""Trim the quoted chain off an inbound reply.

A client answering our mail appends the message it is replying to. Stored
whole, every round trip carries another copy of the thread, and
``conversation.preview`` -- derived from the body in ``append_message`` --
fills with the workspace's own words quoted back at it.

Nothing is lost here. ``raw_messages.raw`` keeps the complete MIME source and
``messages.body_html`` keeps the untrimmed HTML, so the quoted text remains
recoverable; this only decides what the inbox shows and threads on.

Signatures are deliberately *not* touched. "Regards / Ada" is not a quote,
customers routinely put real content after a sign-off, and a trimmer that
guesses at where a person stopped talking loses real messages.
"""

import re

# "On <date> <someone> wrote:". Gmail and Apple Mail fold this across lines
# when the address is long -- which the tokenized ingest address always is --
# so it is matched against a small window of joined lines, not a single one.
_ATTRIBUTION = re.compile(r"^On\b.*\bwrote:\s*$", re.DOTALL)
_ORIGINAL_MESSAGE = re.compile(r"^\s*-{2,}\s*Original Message\s*-{2,}\s*$", re.I)
# Outlook on the web rules off the quote with a long underscore run.
_RULE = re.compile(r"^\s*_{10,}\s*$")
# Outlook for Windows quotes with a bare header block and no separator.
_HEADER_START = re.compile(r"^\s*From:\s*\S")
_HEADER_FOLLOW = re.compile(r"^\s*(Sent|To|Subject|Date|Cc):\s*\S", re.I)
_QUOTED = re.compile(r"^\s*>")

_ATTRIBUTION_WINDOW = 3
_HEADER_WINDOW = 5


def _opens_quote(lines: list[str], index: int) -> bool:
    line = lines[index]

    if _ORIGINAL_MESSAGE.match(line) or _RULE.match(line):
        return True

    if line.lstrip().startswith("On "):
        for last in range(index, min(index + _ATTRIBUTION_WINDOW, len(lines))):
            if _ATTRIBUTION.match("\n".join(lines[index : last + 1]).strip()):
                return True

    if _HEADER_START.match(line):
        window = lines[index + 1 : index + 1 + _HEADER_WINDOW]
        if any(_HEADER_FOLLOW.match(following) for following in window):
            return True

    if _QUOTED.match(line):
        # Only when everything left is quoted. A lone "> ..." mid-message is
        # somebody quoting a phrase to answer it, not the start of the tail.
        remaining = [rest for rest in lines[index:] if rest.strip()]
        if all(_QUOTED.match(rest) for rest in remaining):
            return True

    return False


def strip_quoted(text: str) -> str:
    """The part of ``text`` the sender actually wrote.

    Returns ``text`` unchanged when nothing looks quoted, and -- importantly
    -- also when trimming would leave nothing behind. A reply that is only a
    quote is still a real message; turning it into an empty one would lose
    it, so the quote is kept in that case.
    """
    if not text:
        return text

    lines = text.splitlines()
    for index in range(len(lines)):
        if _opens_quote(lines, index):
            kept = "\n".join(lines[:index]).rstrip()
            return kept if kept.strip() else text
    return text
