"""Strip the obvious personal data out of a visitor's message before it leaves.

This is pattern matching, and the honest description of pattern matching is
that it reduces routine leakage of things a visitor volunteered -- an
address typed into a support question, a card number pasted in a panic. It
is **not** a guarantee, and nothing downstream should be designed as though
it were.

The failure mode worth avoiding is over-redaction. A question with its
nouns replaced by placeholders is a question the model cannot answer, so
these patterns are deliberately narrow: an order number stays, a version
string stays, a duration stays. Only shapes that are almost never anything
else are replaced.

A caller may skip redaction entirely when the workspace has configured a
``base_url`` of its own (spec D6): the text never leaves their deployment,
so redacting it costs answer quality and buys nothing.
"""

import re

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
# Long enough runs of digits, optionally grouped, to be a card or an
# account. Fifteen digits minimum keeps order numbers and years out.
# Crucially: the last digit has no optional separator after it, so the
# space between card and following word is preserved.
_CARD = re.compile(r"\b(?:\d[ ,.-]?){14,18}\d\b")
# An international prefix with +CC, or a leading 0 with separators, or
# digit groups with required separators. Requires actual phone-like structure
# to avoid matching bare runs like account or order numbers or dates.
# All quantifiers are bounded to prevent catastrophic backtracking on
# visitor-supplied input (e.g. long logs or CSV data pasted into questions).
# The 0-prefix requires at least one separator to exclude structureless IDs,
# accepting that bare formats like 02079460958 go unredacted (best-effort only).
# The separated format requires word boundaries to avoid matching within
# date patterns like 2024-0042 or case IDs like 2023-45678.
_PHONE = re.compile(
    r"(?:"
    r"\+\d{1,3}(?:[ ,.-]?\d{1,5}){1,4}"  # +CC with 1-4 digit groups (bounded)
    r"|"
    r"0\d{0,4}[ ,.-]\d{1,6}(?:[ ,.-]\d{1,6}){0,2}"  # 0 prefix: up to 3 groups of digits
    r"|"
    r"(?:\(?\d{3}\)?[ ,.-]){2,3}\d{4}\b"  # Separated: 3-digit groups, final 4
    r")"
)


def redact(text: str) -> str:
    """``text`` with emails, card-like runs and telephone numbers replaced.

    Order matters: cards are matched before telephone numbers, because a
    sixteen-digit card also satisfies a permissive phone pattern and the
    more specific label is the more useful one to a reader of the audit.
    """
    redacted = _EMAIL.sub("[email]", text)
    redacted = _CARD.sub("[number]", redacted)
    return _PHONE.sub("[phone]", redacted)
