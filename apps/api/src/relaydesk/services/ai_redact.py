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

Skipped entirely when the workspace has configured a ``base_url`` of its
own (spec D6): the text never leaves their deployment, so redacting it
costs answer quality and buys nothing.
"""

import re

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
# Long enough runs of digits, optionally grouped, to be a card or an
# account. Fifteen digits minimum keeps order numbers and years out.
_CARD = re.compile(r"\b(?:\d[ -]?){15,19}\b")
# An international prefix, or a run of digits with separators long enough
# to be a telephone number rather than a quantity.
_PHONE = re.compile(r"(?:\+\d{1,3}[ -]?)?(?:\(?\d{2,5}\)?[ -]?){2,4}\d{2,4}")


def redact(text: str) -> str:
    """``text`` with emails, card-like runs and telephone numbers replaced.

    Order matters: cards are matched before telephone numbers, because a
    sixteen-digit card also satisfies a permissive phone pattern and the
    more specific label is the more useful one to a reader of the audit.
    """
    redacted = _EMAIL.sub("[email]", text)
    redacted = _CARD.sub("[number]", redacted)
    return _PHONE.sub("[phone]", redacted)
