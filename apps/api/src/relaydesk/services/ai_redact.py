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

This implementation uses a token-based scanner to avoid regex backtracking:
each token is checked independently with bounded, anchored patterns rather
than scanning the full message with nested quantifiers.

Known limitation, recorded rather than hidden: two numbers written adjacent
with nothing between them but spaces can still be mis-grouped, and the tail
of the second printed in the clear -- "020 7946 0958 07700 900123" redacts
as "[number] 900123", the sixteen digits of the first four groups being a
credible card. A line break between them is enough to separate them, and so
is any punctuation; only the bare-space case is ambiguous, and it is
ambiguous to a reader too. Widening the scanner to resolve it costs more in
over-redaction than the case is worth.
"""

import re


def redact(text: str) -> str:
    """``text`` with emails, card-like runs and telephone numbers replaced.

    Uses a token-based scanner: splits on whitespace, checks each token
    independently, handles multi-token sequences (like "4111 1111 1111 1111")
    with bounded lookahead. Linear time, no catastrophic backtracking.
    """
    tokens = re.split(r"(\s+)", text)
    result = []
    i = 0

    while i < len(tokens):
        token = tokens[i]

        # Preserve whitespace
        if not token or re.match(r"\s+$", token):
            result.append(token)
            i += 1
            continue

        # Check if token should be redacted, with multi-token lookahead
        redacted, tokens_consumed = _redact_token(token, tokens, i)
        result.append(redacted)
        # Skip consumed whitespace and tokens
        i += 1 + 2 * tokens_consumed

    return "".join(result)


# A label glued to a number tells you what the number is, and the question
# is which way to fail when the label is unfamiliar. Peeling ANY "word:"
# destroyed labelled identifiers -- "amount:1,234,567.89" became
# "amount:[phone]", likewise "serial:", "sku#", "po#". Peeling only a list
# of known PII labels fixed that and failed the other way: "mailto:",
# "contact:", "whatsapp:", "number:" and a dozen others sailed through with
# real telephone numbers and addresses attached.
#
# So the list that has to be right is the one naming things that are NOT
# personal data, and an unfamiliar label fails toward redaction. That is the
# safer direction here: an over-redacted "widget:1234567890" costs one
# unanswerable question, where an under-redacted "whatsapp:555-123-4567"
# sends a stranger's number to a third party.
_LABEL_RE = re.compile(r"[A-Za-z]{1,12}\d?\.?[:#=]")
_NON_PII_LABEL_RE = re.compile(
    r"(?:amount|total|sum|price|cost|qty|quantity|ref|reference|serial|sn|sku"
    r"|po|order|lot|batch|invoice|inv|account|acct|id|case|ticket|item|part"
    r"|seq|line|row|page|version|build|rev|job|task|issue|bug|step|port|pid)"
    r"\d?\.?[:#=]",
    re.IGNORECASE,
)

# Punctuation that can sit either side of a number without being part of it.
# "." and "," appear in both roles, but only ever as separators in the MIDDLE
# of a number, so peeling them at the edges alone is safe. Angle brackets are
# never number-internal; round and square brackets are handled separately
# because "(555) 123-4567" needs its parens kept.
_EDGE_PUNCT = "\"'`;:!?.,<>«»“”‘’"
_CLOSER = {"(": ")", "[": "]"}
_OPENER = {")": "(", "]": "["}

# What counts as a separator between the digit groups of a card or phone
# number, for both "strip these out before counting digits" and "does this
# have a separator at all" checks. \s is the same whitespace class the
# tokenizer split on (tabs, newlines, non-breaking spaces -- not just the
# ASCII space), so a number joined across a multi-token window can never
# leak just because its gap character wasn't in some narrower, separately
# maintained list. The en and em dashes are here because Word and Gmail
# rewrite a typed hyphen into one without asking.
_SEPARATOR_RE = re.compile(r"[\s,.\-–—()]")

_SPACE_RE = re.compile(r"\s+")
_LINE_BREAK_RE = re.compile(r"[\n\r  ]")
_DIGIT_GROUP_RE = re.compile(r"[\d,.\-–—() ]+")

# Five groups, because six ate ordinary numeric prose -- a row of quantities,
# a CSV paste, a log line. The one number that genuinely needs six is an
# international one written "+33 1 42 68 53 00", and there the "+" is the
# evidence that earns the extra group.
_MAX_WINDOW = 5
_MAX_WINDOW_PLUS = 6

_MAX_EDGE_PEELS = 16

# The label peel may fire at most this many times on one token. A fixed
# vocabulary makes deep nesting implausible; this makes it impossible.
_MAX_LABEL_DEPTH = 2


def _is_space(token: str) -> bool:
    return bool(_SPACE_RE.fullmatch(token))


def _is_digit_group(token: str) -> bool:
    """Digits and separators only, and at least one digit."""
    return bool(_DIGIT_GROUP_RE.fullmatch(token)) and any(c.isdigit() for c in token)


def _split_edges(token: str) -> tuple[str, str, str]:
    """``token`` as (leading punctuation, core, trailing punctuation).

    Brackets are peeled only when they are NOT part of the number: an
    unmatched one, or a matched pair around something that is not a digit
    group at all. "(555)" keeps its parens, because they are how the area
    code was written and stripping them loses the grouping that tells a
    phone number from an account number; "(wren@lantern.co)" loses them,
    because an address in brackets is still an address.
    """
    start, end = 0, len(token)
    peeled = True
    # Bounded because the `in token[start:end]` balance test is linear, and
    # an unbounded peel over a long run of brackets is therefore quadratic.
    # Real punctuation around a number does not run deeper than this.
    for _ in range(_MAX_EDGE_PEELS):
        if not peeled or start >= end:
            break
        peeled = False

        lead_char, trail_char = token[start], token[end - 1]
        if (
            end - start > 2
            and lead_char in _CLOSER
            and trail_char == _CLOSER[lead_char]
            and not _is_digit_group(token[start + 1 : end - 1])
        ):
            start, end = start + 1, end - 1
            peeled = True
            continue

        # "Is this bracket unmatched?" is a question about counts, not about
        # presence: "((555)" contains a ")" but still has one "(" too many,
        # and testing for presence left the outer one glued to the number.
        if lead_char in _EDGE_PUNCT or (
            lead_char in _CLOSER
            and token.count(lead_char, start, end)
            > token.count(_CLOSER[lead_char], start, end)
        ):
            start += 1
            peeled = True
            continue

        if trail_char in _EDGE_PUNCT or (
            trail_char in _OPENER
            and token.count(trail_char, start, end)
            > token.count(_OPENER[trail_char], start, end)
        ):
            end -= 1
            peeled = True

    return token[:start], token[start:end], token[end:]


def _redact_token(token: str, tokens: list, index: int) -> tuple:
    """Check if a token should be redacted.

    Returns (redacted_token, additional_tokens_consumed).
    """
    lead, core, trail = _split_edges(token)
    if not core:
        return token, 0

    # A token that ENDS in punctuation also ends any multi-token number, so
    # the window must not be allowed to read past it.
    window = tokens[: index + 1] if trail else tokens
    redacted, consumed = _redact_core(core, window, index, depth=0)
    if redacted == core:
        return token, 0
    return lead + redacted + trail, consumed


def _redact_core(core: str, tokens: list, index: int, depth: int) -> tuple:
    """Decide the fate of one token with its surrounding punctuation removed.

    Every guard below is anchored to the whole string it is given, which is
    why the edges have to come off first: "case ID 2023-45678." reached the
    phone rule with its full stop still attached, and a trailing "." reads
    as a group separator.
    """
    label_match = _LABEL_RE.match(core)
    if (
        label_match
        and depth < _MAX_LABEL_DEPTH
        and not _NON_PII_LABEL_RE.fullmatch(label_match.group())
    ):
        remainder = core[label_match.end():]
        if remainder:
            inner, consumed = _redact_core(remainder, tokens, index, depth + 1)
            if inner != remainder:
                return label_match.group() + inner, consumed

    if "@" in core and _is_email(core):
        return "[email]", 0

    # Any token containing a letter is left alone (keeps dates, versions, IDs)
    if re.search(r"[a-zA-Z]", core):
        return core, 0

    # ISO dates (YYYY-MM-DD) are left alone
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", core):
        return core, 0

    # IP addresses (X.X.X.X format) are left alone
    if _looks_like_ip(core):
        return core, 0

    # Date-like patterns (4-5 digits, dash, 2-5 digits) are left alone
    if re.fullmatch(r"\d{4,5}-\d{2,5}", core):
        return core, 0

    # A figure with both a thousands separator and a decimal point is money,
    # not a telephone number.
    if _looks_like_decimal(core.strip("()")):
        return core, 0

    return _check_number(core, tokens, index)


def _is_email(token: str) -> bool:
    """Check if token is a valid email address."""
    return bool(re.fullmatch(r"[\w.+-]+@[\w-]+\.[\w.-]+", token))


def _looks_like_decimal(token: str) -> bool:
    """A thousands-grouped figure with a fractional part: 1,234,567.89."""
    return bool(re.fullmatch(r"\d{1,3}(?:,\d{3})+\.\d+|\d+\.\d{1,2}", token))


def _digit_windows(core: str, tokens: list, index: int, max_window: int) -> list:
    """Every run of digit-group tokens starting here, in preference order.

    Two orderings, concatenated. Windows that cross no line break come
    first, longest first; then those that do, longest first. A line break
    usually separates two numbers -- a card on one line, a telephone number
    on the next -- but it can also fall inside one that has been wrapped, so
    it is a preference rather than a boundary. Taking it as a hard boundary
    would leak a wrapped card whole; ignoring it, as this did, swallowed the
    following number's first group and printed the rest in the clear.

    Longest first WITHIN each class, because a window that only ever tried
    its maximum length abandoned the position whenever the widest run was
    the wrong shape: "card 4111 1111 1111 1111 2026" is five groups and
    twenty digits, matching nothing, and giving up there printed "4111".
    """
    if not _is_digit_group(core):
        return [[], []]

    plain, crossing = [(core, 0, "")], []
    combined = core
    count = 1
    pos = index + 1
    crossed = False
    while count < max_window and pos + 1 < len(tokens):
        gap = tokens[pos]
        if not _is_space(gap):
            break
        next_lead, next_core, next_trail = _split_edges(tokens[pos + 1])
        if next_lead or not _is_digit_group(next_core):
            break
        combined += gap + next_core
        count += 1
        crossed = crossed or bool(_LINE_BREAK_RE.search(gap))
        (crossing if crossed else plain).append((combined, count - 1, next_trail))
        pos += 2
        if next_trail:
            break

    plain.reverse()
    crossing.reverse()
    return [plain, crossing]


# Cards come in fifteen, sixteen and nineteen digits. Seventeen and
# eighteen are accepted because the range is a sanity check rather than a
# card catalogue, but they are not real card lengths -- a window totalling
# eighteen has eaten something that follows, as "4111 1111 1111 1111 12"
# eats an expiry month over the sixteen-digit card in front of it.
#
# So a canonical total beats a non-canonical one. Between two canonical
# totals the LONGER window wins, because it is the whole card: preferring
# the shorter one printed the last three digits of every nineteen-digit
# card in the clear.
_CANONICAL_CARD_LENGTHS = frozenset({15, 16, 19})


def _check_number(core: str, tokens: list, index: int) -> tuple:
    """Redact this token, or a run starting at it, as a card or a phone number.

    Card before phone at every window, because their digit ranges do not
    overlap (15-19 against 9-14) and trying phone first would match the
    first three groups of a four-group card and print the fourth in the
    clear.

    Both are tried across the windows that cross no line break before
    either is tried across the windows that do. A line break usually
    separates two numbers -- a card on one line, a telephone number on the
    next -- but it can also fall inside one that has been wrapped, so it is
    a preference rather than a boundary. Taking it as a hard boundary would
    leak a wrapped card whole; ignoring it swallowed the following number's
    first group and printed the rest. Preferring one class wholesale, and
    not merely within a single check, is what keeps a card window on the
    far side of a line break from beating a phone window on this side.
    """
    plus = core.startswith("+")
    probe = core[1:] if plus else core
    max_window = _MAX_WINDOW_PLUS if plus else _MAX_WINDOW

    for windows in _digit_windows(probe, tokens, index, max_window):
        card = _best_card(windows)
        if card is not None:
            return card
        phone = _best_phone(windows, plus=plus)
        if phone is not None:
            return phone
    return core, 0


def _best_card(windows: list) -> tuple | None:
    """The most card-shaped window in this class, or None."""
    matches = []
    for combined, consumed, trail in windows:
        digits = _strip_separators(combined)
        if not _looks_like_card_digits(digits):
            continue
        # A bare run of digits with no grouping at all is only a card at the
        # lengths that are unambiguously one; otherwise it is somebody's
        # order number.
        if (
            consumed == 0
            and not _SEPARATOR_RE.search(combined)
            and len(digits) not in (15, 16, 19)
        ):
            continue
        canonical = len(digits) in _CANONICAL_CARD_LENGTHS
        matches.append(((0 if canonical else 1, -consumed), consumed, trail))
    if not matches:
        return None
    _, consumed, trail = min(matches, key=lambda match: match[0])
    return "[number]" + trail, consumed


def _best_phone(windows: list, *, plus: bool) -> tuple | None:
    """The longest phone-shaped window in this class, or None."""
    for combined, consumed, trail in windows:
        digits = _strip_separators(combined)
        if not re.fullmatch(r"\d+", digits):
            continue
        if not 9 <= len(digits) <= 14:
            continue
        # Grouping (or a country code) is what separates a phone number from
        # a nine-digit account number.
        if not plus and not _SEPARATOR_RE.search(combined):
            continue
        return "[phone]" + trail, consumed
    return None


def _strip_separators(token: str) -> str:
    """Remove digit-group separators (whitespace, commas, dots, dashes, parens)."""
    return _SEPARATOR_RE.sub("", token)


def _looks_like_card_digits(digits: str) -> bool:
    """Check if digit string looks like a card (15-19 digits)."""
    return bool(re.fullmatch(r"\d+", digits)) and 15 <= len(digits) <= 19


def _looks_like_ip(token: str) -> bool:
    """Check if token looks like an IP address (192.168.1.100)."""
    parts = token.split(".")
    if len(parts) != 4:
        return False
    return all(re.fullmatch(r"\d{1,3}", part) for part in parts)
