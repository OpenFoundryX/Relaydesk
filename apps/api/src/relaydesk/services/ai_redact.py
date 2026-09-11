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


_LABEL_RE = re.compile(r"[A-Za-z]{1,12}[:#=]")

# Punctuation that can sit either side of a number without being part of it.
# Deliberately excludes "(", ")" and "-": those are group separators inside a
# real number -- "(555) 123-4567" -- and peeling them would take the number
# apart. "." and "," appear in both roles, but only ever as separators in the
# MIDDLE of a number, so peeling them at the edges alone is safe.
_EDGE_PUNCT = "\"'`;:!?.,\u00ab\u00bb\u201c\u201d\u2018\u2019"

# What counts as a separator between the digit groups of a card or phone
# number, for both "strip these out before counting digits" and "does this
# have a separator at all" checks. \s is the same whitespace class the
# tokenizer split on (tabs, newlines, non-breaking spaces -- not just the
# ASCII space), so a number joined across a multi-token window can never
# leak just because its gap character wasn't in some narrower, separately
# maintained list. This one definition is the only place that list lives.
_SEPARATOR_RE = re.compile(r"[\s,.\-()]")

_SPACE_RE = re.compile(r"\s+")
_DIGIT_GROUP_RE = re.compile(r"[\d,.\-() ]+")

# Six tokens, not five. A number written "+33 1 42 68 53 00" is six groups,
# and a window that stopped at five would redact the first five and print the
# last two digits in the clear -- a partial leak is the one outcome worse
# than either redacting or not.
_MAX_WINDOW = 6


def _is_space(token: str) -> bool:
    return bool(_SPACE_RE.fullmatch(token))


def _is_digit_group(token: str) -> bool:
    """Digits and separators only, and at least one digit.

    The digit requirement stops a run of dashes or dots being treated as the
    start of a number.
    """
    return bool(_DIGIT_GROUP_RE.fullmatch(token)) and any(c.isdigit() for c in token)


def _split_edges(token: str) -> tuple[str, str, str]:
    """``token`` as (leading punctuation, core, trailing punctuation)."""
    start = 0
    while start < len(token) and token[start] in _EDGE_PUNCT:
        start += 1
    end = len(token)
    while end > start and token[end - 1] in _EDGE_PUNCT:
        end -= 1
    return token[:start], token[start:end], token[end:]


def _redact_token(token: str, tokens: list, index: int) -> tuple:
    """Check if a token should be redacted.

    Returns (redacted_token, additional_tokens_consumed).
    """
    # A leading label glued straight onto PII ("phone:555-123-4567",
    # "card#4111111111111111") would otherwise be caught whole by the
    # letter-guard below and pass through unredacted. Peel the label,
    # check the remainder on its own, and re-attach the label to
    # whatever comes back. An identifier like "INV-2024-0042" has no
    # ":"/"#"/"=" after its letters, so it never matches this and stays
    # protected by the letter-guard as before.
    label_match = _LABEL_RE.match(token)
    if label_match:
        remainder = token[label_match.end():]
        if remainder:
            redacted_remainder, consumed = _redact_token(remainder, tokens, index)
            if redacted_remainder != remainder:
                return label_match.group() + redacted_remainder, consumed

    # Punctuation around a number is not part of it. Without this a quoted
    # card or a phone number ending a sentence goes out in the clear,
    # because every check below is anchored to the whole token. Peeling it
    # here also stops the full stop in "call 555-123-4567." being eaten as
    # though it were a group separator.
    lead, core, trail = _split_edges(token)
    if core and (lead or trail):
        # A token that ENDS in punctuation also ends any multi-token number,
        # so the window must not be allowed to read past it.
        window = tokens[: index + 1] if trail else tokens
        redacted_core, consumed = _redact_token(core, window, index)
        if redacted_core != core:
            return lead + redacted_core + trail, consumed

    # Email: must contain @ and match email pattern
    if "@" in token and _is_email(token):
        return "[email]", 0

    # Any token containing a letter is left alone (keeps dates, versions, IDs)
    if re.search(r"[a-zA-Z]", token):
        return token, 0

    # ISO dates (YYYY-MM-DD) are left alone
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", token):
        return token, 0

    # IP addresses (X.X.X.X format) are left alone
    if _looks_like_ip(token):
        return token, 0

    # Date-like patterns (4-5 digits, dash, 2-5 digits) are left alone
    if re.fullmatch(r"\d{4,5}-\d{2,5}", token):
        return token, 0

    result, consumed = _check_card(token, tokens, index)
    if result != token:
        return result, consumed

    result, consumed = _check_phone(token, tokens, index)
    if result != token:
        return result, consumed

    return token, 0


def _is_email(token: str) -> bool:
    """Check if token is a valid email address."""
    return bool(re.fullmatch(r"[\w.+-]+@[\w-]+\.[\w.-]+", token))


def _digit_windows(core: str, tokens: list, index: int) -> list:
    """Every run of digit-group tokens starting here, longest first.

    Each entry is ``(combined_text, extra_tokens_consumed, trailing_punct)``.

    Longest first, and the caller takes the first that matches, because a
    window that only ever tried its maximum length would abandon the
    position whenever the widest run happened to be the wrong shape.
    "card 4111 1111 1111 1111 2026" is five groups; the five-group total is
    twenty digits and matches nothing, and giving up there printed "4111" in
    the clear. The four-group prefix is the card.
    """
    if not _is_digit_group(core):
        return []

    windows = [(core, 0, "")]
    combined = core
    count = 1
    pos = index + 1
    while count < _MAX_WINDOW and pos + 1 < len(tokens):
        gap = tokens[pos]
        if not _is_space(gap):
            break
        next_lead, next_core, next_trail = _split_edges(tokens[pos + 1])
        if next_lead or not _is_digit_group(next_core):
            break
        combined += gap + next_core
        count += 1
        windows.append((combined, count - 1, next_trail))
        pos += 2
        if next_trail:
            break

    windows.reverse()
    return windows


def _check_card(core: str, tokens: list, index: int) -> tuple:
    """Check if this token, or a run starting at it, is a card number."""
    for combined, consumed, trail in _digit_windows(core, tokens, index):
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
        return "[number]" + trail, consumed
    return core, 0


def _check_phone(core: str, tokens: list, index: int) -> tuple:
    """Check if this token, or a run starting at it, is a telephone number.

    The international "+" prefix is handled here rather than in a second
    walk of its own: it changes only whether grouping is required, not how
    the run is collected, and two walks with different counting conventions
    was how the last round's partial leaks got in.
    """
    plus = core.startswith("+")
    probe = core[1:] if plus else core
    for combined, consumed, trail in _digit_windows(probe, tokens, index):
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
    return core, 0


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
