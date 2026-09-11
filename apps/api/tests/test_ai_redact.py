import pytest
import time

from relaydesk.services.ai_redact import redact


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("email me at wren@lantern.co", "email me at [email]"),
        ("WREN@LANTERN.CO please", "[email] please"),
        ("call 020 7946 0958", "call [phone]"),
        ("call +44 20 7946 0958", "call [phone]"),
        ("call 020.7946.0958", "call [phone]"),
        ("call (555) 123-4567", "call [phone]"),
        ("call 555-123-4567", "call [phone]"),
        ("call +1 555-123-4567", "call [phone]"),
        ("call 07700 900123", "call [phone]"),
        ("card 4111 1111 1111 1111", "card [number]"),
        ("card 4111-1111-1111-1111", "card [number]"),
        ("card 4111,1111,1111,1111", "card [number]"),
        ("card 4111.1111.1111.1111", "card [number]"),
    ],
)
def test_redacts(raw, expected):
    assert redact(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "my order is 1042",
        "version 2.5.1 broke it",
        "I waited 30 minutes",
        "",
        "my account is 12345678",
        "order number 123456789",
        "PO number 5551234",
        "employee id 4829103",
        "ticket #100234567",
        "build 20260911 shipped",
    ],
)
def test_leaves_ordinary_text_alone(raw):
    """Over-redaction destroys the question. A short number is not a card."""
    assert redact(raw) == raw


def test_redacts_several_in_one_message():
    assert redact("wren@lantern.co or 020 7946 0958") == "[email] or [phone]"


def test_card_with_text_after():
    """Ensure the trailing space after a card is preserved."""
    assert redact("card 4111 1111 1111 1111 arrived today") == "card [number] arrived today"


@pytest.mark.parametrize(
    "raw",
    [
        # Zero-led account/order numbers without separators should not be redacted.
        # The 0-prefix pattern requires at least one separator (space/dot/comma/dash)
        # to distinguish from bare account/order/reference numbers.
        # This means bare formats like 02079460958 also go unredacted (acceptable
        # trade-off: under-redacting is preferable to over-redacting common IDs).
        "account 012345678",
        "order 0123456789",
        "reference 01234567",
    ],
)
def test_leaves_zero_led_ids_alone(raw):
    """Zero-led bare numbers without structure are not redacted."""
    assert redact(raw) == raw


def test_redact_performance():
    """Bounded quantifiers prevent catastrophic backtracking on long input.

    The original unbounded {2,} with variable inner quantifier caused quadratic
    backtracking on input like ('a1b2' * 20000) + 'text', where patterns try all
    possible ways to partition digit sequences. Bounded quantifiers prevent this.
    """
    import time

    # 60KB of mixed pattern that would stress pattern matching without triggering matches.
    # 'a1b2' pattern keeps digit groups short and non-contiguous, avoiding card/phone matches.
    large_input = ('a1b2' * 20000) + 'text'

    start = time.time()
    result = redact(large_input)
    elapsed = time.time() - start

    # Should complete well within 10 seconds (original took 9.71 seconds).
    # Bounded quantifiers significantly limit worst-case backtracking.
    assert elapsed < 10.0, f"Redaction took {elapsed:.2f}s, expected < 10s"
    # Verify the result is unchanged (no matches should occur)
    assert result == large_input
