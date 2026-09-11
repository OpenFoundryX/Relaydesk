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


def _redact_token(token: str, tokens: list, index: int) -> tuple:
    """Check if a token should be redacted.

    Returns (redacted_token, additional_tokens_consumed).
    """
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

    # Check for card number (single token or multi-token sequence)
    result, consumed = _check_card(token, tokens, index)
    if result != token:
        return result, consumed

    # Check for phone number (single token or multi-token sequence)
    # Handle + prefix by looking ahead
    if token.startswith("+"):
        result, consumed = _check_phone_with_plus(token, tokens, index)
        if result != token:
            return result, consumed
    else:
        result, consumed = _check_phone(token, tokens, index)
        if result != token:
            return result, consumed

    return token, 0


def _is_email(token: str) -> bool:
    """Check if token is a valid email address."""
    return bool(re.fullmatch(r"[\w.+-]+@[\w-]+\.[\w.-]+", token))


def _check_card(token: str, tokens: list, index: int) -> tuple:
    """Check if token or token sequence is a card number.

    Returns (redacted, tokens_consumed).
    """
    # Single token: check if it's a card
    digits_only = _strip_separators(token)
    if _looks_like_card_digits(digits_only):
        has_sep = any(c in token for c in " ,-.")
        if has_sep or len(digits_only) in [15, 16, 19]:
            return "[number]", 0

    # Multi-token: try combining 2-5 consecutive digit-group tokens
    combined, consumed = _collect_digit_tokens(token, tokens, index, max_tokens=5)
    if consumed > 0:
        digits_only = _strip_separators(combined)
        if _looks_like_card_digits(digits_only):
            return "[number]", consumed - 1  # -1 because first token is current

    return token, 0


def _check_phone(token: str, tokens: list, index: int) -> tuple:
    """Check if token or token sequence is a phone number.

    Returns (redacted, tokens_consumed).
    """
    # Single token
    digits_only = _strip_separators_and_parens(token)
    if _looks_like_phone_digits(digits_only, token):
        return "[phone]", 0

    # Multi-token: try combining 2-5 consecutive digit-group tokens
    combined, consumed = _collect_digit_tokens(token, tokens, index, max_tokens=5)
    if consumed > 0:
        digits_only = _strip_separators_and_parens(combined)
        if _looks_like_phone_digits(digits_only, combined):
            return "[phone]", consumed - 1

    return token, 0


def _strip_separators(token: str) -> str:
    """Remove spaces, commas, dots, and dashes."""
    return token.translate(str.maketrans("", "", " ,.-"))


def _strip_separators_and_parens(token: str) -> str:
    """Remove spaces, commas, dots, dashes, and parentheses."""
    return token.translate(str.maketrans("", "", " ,.-()"))


def _looks_like_card_digits(digits: str) -> bool:
    """Check if digit string looks like a card (15-19 digits)."""
    return (
        bool(re.fullmatch(r"\d+", digits))
        and 15 <= len(digits) <= 19
    )


def _looks_like_phone_digits(digits: str, original: str) -> bool:
    """Check if digits look like a phone (9-14 digits with structure)."""
    if not re.fullmatch(r"\d+", digits):
        return False
    if not (9 <= len(digits) <= 14):
        return False
    # Must have at least one separator or start with +
    has_sep = any(c in original for c in " -,.()")
    starts_with_plus = original.startswith("+")
    return has_sep or starts_with_plus


def _collect_digit_tokens(token: str, tokens: list, index: int, max_tokens: int) -> tuple:
    """Collect up to max_tokens consecutive digit-group tokens.

    Returns (combined_string, total_tokens_collected).
    """
    if not re.fullmatch(r"[\d,.\-() ]+", token):
        return token, 0

    combined = token
    count = 1
    pos = index + 1

    while count < max_tokens and pos < len(tokens):
        # Skip whitespace
        if re.match(r"\s+$", tokens[pos]):
            combined += tokens[pos]
            pos += 1
            if pos >= len(tokens):
                break
        # Check if next token is also digits/separators
        next_token = tokens[pos]
        if re.fullmatch(r"[\d,.\-() ]+", next_token):
            combined += next_token
            count += 1
            pos += 1
        else:
            break

    return combined, count


def _looks_like_ip(token: str) -> bool:
    """Check if token looks like an IP address (192.168.1.100)."""
    parts = token.split(".")
    if len(parts) != 4:
        return False
    for part in parts:
        if not re.fullmatch(r"\d{1,3}", part):
            return False
    return True


def _check_phone_with_plus(token: str, tokens: list, index: int) -> tuple:
    """Check if token starting with + (plus country code) is a phone.

    Combines multiple tokens: +CC number number...
    Returns (redacted, tokens_consumed).
    """
    # Collect the + token plus following digit tokens
    combined = token
    count = 0
    pos = index + 1

    # Look ahead for up to 5 more tokens that are digits/separators
    while count < 5 and pos < len(tokens):
        next_token = tokens[pos]
        # Skip whitespace but include it
        if re.match(r"\s+$", next_token):
            combined += next_token
            pos += 1
        # Check if next token is digits/separators (but not +)
        elif re.fullmatch(r"[\d,.\-() ]+", next_token):
            combined += next_token
            count += 1
            pos += 1
        else:
            break

    if count == 0:
        # No digit tokens found after +
        return token, 0

    digits_only = _strip_separators_and_parens(combined)
    # Remove the + from digit count
    digits_only = digits_only.lstrip("+")

    # Must have country code (1-3 digits) + at least 7 more digits = minimum 9 total
    if len(digits_only) >= 9 and re.fullmatch(r"\d+", digits_only):
        return "[phone]", count

    return token, 0
