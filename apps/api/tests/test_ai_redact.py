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


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("4111 1111 1111 1111\n020 7946 0958", "[number]\n[phone]"),
        ("020 7946 0958\n020 7946 0959", "[phone]\n[phone]"),
    ],
)
def test_a_line_break_between_two_numbers_is_a_boundary(message, expected):
    """Contact details on consecutive lines are one message, not one number.

    Treating every whitespace as a separator -- needed so a wrapped card
    still redacts -- let a card window cross the line break, swallow the
    following number's first group and print the rest in the clear.
    """
    assert redact(message) == expected


def test_a_wrapped_card_still_redacts():
    """The other side of the same trade: the line break is a preference, not a wall."""
    assert redact("4111 1111\n1111 1111") == "[number]"


def test_a_card_does_not_swallow_the_expiry_that_follows_it():
    """Eighteen digits is in range; sixteen is the card. The canonical length wins."""
    assert redact("4111 1111 1111 1111 12 26") == "[number] 12 26"


@pytest.mark.parametrize(
    "message",
    [
        "amount:1,234,567.89",
        "total:9876543.21",
        "ref:1234-5678-9012",
        "serial:1234-5678-9012",
        "sku#0000-1111-2222",
        "po#100-200-300",
        "order:012 345 678",
    ],
)
def test_a_label_that_is_not_pii_protects_what_follows_it(message):
    """The label is evidence, not just a prefix to strip.

    Peeling any `word:` closed the glued-PII leak but destroyed labelled
    identifiers -- exactly the shapes the module promises to keep. These
    labels say "not personal data", and are read that way.
    """
    assert redact(message) == message


@pytest.mark.parametrize("message", ["a:" * 1000, "ab#" * 1000, "x=" * 1000])
def test_a_crafted_label_chain_does_not_crash(message):
    """This runs on an anonymous endpoint; RecursionError here is a 500."""
    redact(message)


@pytest.mark.parametrize(
    "message",
    [
        "case ID 2023-45678.",
        "order 0123456789.",
        "my server is 192.168.1.100.",
        "192.168.1.100,",
    ],
)
def test_a_full_stop_does_not_destroy_a_protected_shape(message):
    """Every guard is anchored to the whole token, so the edges come off first.

    A trailing "." reads as a group separator and pushed each of these into
    phone range -- each one a must-keep shape one full stop from ruin.
    """
    assert redact(message) == message


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("<wren@lantern.co>", "<[email]>"),
        ("(wren@lantern.co)", "([email])"),
        ("my email (wren@lantern.co) is old", "my email ([email]) is old"),
        ("call 555-123-4567.)", "call [phone].)"),
        ("my card (4111 1111 1111 1111) expires soon", "my card ([number]) expires soon"),
    ],
)
def test_brackets_around_a_number_survive_it(message, expected):
    """Brackets were absorbed into the number and vanished with it."""
    assert redact(message) == expected


def test_parentheses_that_are_part_of_the_number_are_kept():
    """The counter-case: "(555)" is how an area code is written."""
    assert redact("(555) 123-4567") == "[phone]"


def test_an_en_dash_separates_digit_groups_like_a_hyphen():
    """Word and Gmail rewrite a typed hyphen into one without asking."""
    assert redact("555–123–4567") == "[phone]"


@pytest.mark.parametrize(
    ("message", "expected"),
    [("tel.:555-123-4567", "tel.:[phone]"), ("phone2:555-123-4567", "phone2:[phone]")],
)
def test_label_variants_people_actually_type(message, expected):
    assert redact(message) == expected


def test_a_money_figure_is_not_a_telephone_number():
    assert redact("refund of 1,234,567.89 please") == "refund of 1,234,567.89 please"


def test_a_six_group_list_of_numbers_is_not_a_phone_number():
    """Six space-separated groups is a CSV paste or a list far more often
    than a telephone number. The one number that genuinely needs six groups
    is international, and there the "+" is the evidence that earns it --
    which is why the wider window is granted only to a "+" prefix.
    """
    assert redact("items 1 2 3 4 5 1000") == "items 1 2 3 4 5 1000"
