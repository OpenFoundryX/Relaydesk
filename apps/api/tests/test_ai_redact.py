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
