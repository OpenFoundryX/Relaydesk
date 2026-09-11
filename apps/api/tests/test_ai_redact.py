import pytest
import time

from relaydesk.services.ai_redact import redact


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Emails
        ("email me at wren@lantern.co", "email me at [email]"),
        ("WREN@LANTERN.CO please", "[email] please"),
        # Phones with various formats
        ("call 020 7946 0958", "call [phone]"),
        ("call +44 20 7946 0958", "call [phone]"),
        ("call 020.7946.0958", "call [phone]"),
        ("call (555) 123-4567", "call [phone]"),
        ("call 555-123-4567", "call [phone]"),
        ("call +1 555-123-4567", "call [phone]"),
        ("call 07700 900123", "call [phone]"),
        ("call +33 1 42 68 53 00", "call [phone]"),
        # Cards with various formats
        ("card 4111 1111 1111 1111", "card [number]"),
        ("card 4111-1111-1111-1111", "card [number]"),
        ("card 4111,1111,1111,1111", "card [number]"),
        ("card 4111111111111111", "card [number]"),
        ("card 378282246310005", "card [number]"),
        # Labels glued straight onto PII
        ("phone:555-123-4567", "phone:[phone]"),
        ("email:foo@bar.com", "email:[email]"),
        ("card#4111111111111111", "card#[number]"),
        # Non-literal (but still whitespace) separators between digit groups
        ("4111 1111\n1111 1111", "[number]"),
        ("020\t7946\t0958", "[phone]"),
        ("call 555\xa0123\xa04567", "call [phone]"),
    ],
)
def test_redacts(raw, expected):
    assert redact(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        # Original test cases
        "my order is 1042",
        "version 2.5.1 broke it",
        "I waited 30 minutes",
        "",
        # New cases: must not be over-redacted
        "my account number is 12345678",
        "order 0123456789",
        "account 012345678",
        "ticket #100234567",
        "case ID 2023-45678",
        "the 2026-09-11 release",
        "my invoice is INV-2024-0042",
        "build 20260911 shipped",
        "1,234,567 dollars",
        "192.168.1.100",
        "SW1A 1AA",
        "09:30:15",
        "1920x1080",
        "price range 100-200 dollars",
    ],
)
def test_leaves_ordinary_text_alone(raw):
    """Over-redaction destroys the question. Any token with a letter is kept."""
    assert redact(raw) == raw


def test_redacts_several_in_one_message():
    assert redact("wren@lantern.co or 020 7946 0958") == "[email] or [phone]"


def test_card_with_text_after():
    """Ensure the trailing space after a card is preserved."""
    assert redact("card 4111 1111 1111 1111 arrived today") == "card [number] arrived today"


@pytest.mark.parametrize(
    ("payload_size", "max_seconds"),
    [
        (20001, 1.0),      # 20KB
        (60003, 1.0),      # 60KB
        (120003, 1.0),     # 120KB
    ],
)
def test_redact_performance(payload_size, max_seconds):
    """Token-based scanner is linear: completes large inputs in <1 second."""
    # Generate pathological input: repetitive digit-letter pattern
    # With regex, ('12-' * 20000) caused 9.71s backtracking
    # Token scanner should handle same in milliseconds
    reps = payload_size // 4  # Each rep is "a1b2" = 4 chars
    large_input = ("a1b2" * reps)[:payload_size] + "text"

    start = time.time()
    result = redact(large_input)
    elapsed = time.time() - start

    assert elapsed < max_seconds, f"Redaction took {elapsed:.3f}s for {payload_size} bytes, expected < {max_seconds}s"
    # Verify the result is unchanged (no matches should occur)
    assert result == large_input


@pytest.mark.parametrize(
    "message",
    [
        "4111 1111\n1111 1111",
        "020\t7946\t0958",
        "call 555\xa0123\xa04567",
    ],
)
def test_a_number_split_by_any_whitespace_is_still_a_number(message):
    """The separator set and the tokenizer must not be able to disagree.

    `redact` splits on `\\s`, so a card broken across a line, a tab-aligned
    column, or a non-breaking space arrives as several tokens exactly as a
    space-separated one does. When the window's own idea of a separator was
    a hand-written list of ASCII characters, each of these went out in full.
    """
    assert message not in redact(message)


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("call 555-123-4567;", "call [phone];"),
        ("call 555-123-4567?", "call [phone]?"),
        ("call 555-123-4567!", "call [phone]!"),
        ('"4111 1111 1111 1111"', '"[number]"'),
        # And the full stop survives rather than being eaten as a separator.
        ("call 555-123-4567.", "call [phone]."),
    ],
)
def test_punctuation_around_a_number_is_not_part_of_it(message, expected):
    """Every check is anchored to a whole token, so the edges must come off first."""
    assert redact(message) == expected


def test_a_card_followed_by_another_number_does_not_leak_its_first_group():
    """The window tries shorter runs rather than abandoning the position.

    Five digit groups in a row is not a card, and a window that only ever
    tried its own maximum length gave up here and emitted "4111" in the
    clear -- the one outcome worse than either redacting or not.
    """
    assert redact("card 4111 1111 1111 1111 2026") == "card [number] 2026"


def test_two_adjacent_phone_numbers_are_both_redacted():
    assert redact("020 7946 0958 555-123-4567") == "[phone] [phone]"


def test_a_six_group_international_number_is_redacted_whole():
    """Five groups would have redacted the first five and printed "00"."""
    assert redact("+33 1 42 68 53 00") == "[phone]"


@pytest.mark.parametrize(
    "message",
    [
        "phone:555-123-4567",
        "email:foo@bar.com",
        "card#4111111111111111",
        "SSN:123-45-6789",
    ],
)
def test_a_label_glued_to_pii_does_not_shield_it(message):
    """The letter-guard protects "INV-2024-0042"; it must not protect this."""
    assert message not in redact(message)


@pytest.mark.parametrize(
    "message",
    [
        "ticket #100234567",
        "my invoice is INV-2024-0042",
        "case ID 2023-45678",
        "the 2026-09-11 release",
        "SW1A 1AA",
        "09:30:15",
        "version 2.5.1 broke it",
        "price range 100-200 dollars",
    ],
)
def test_narrowing_the_letter_guard_did_not_widen_redaction(message):
    """The companion to the test above: peeling labels must cost nothing here."""
    assert redact(message) == message
