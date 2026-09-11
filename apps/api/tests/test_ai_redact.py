import pytest

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
        ("call 02079460958", "call [phone]"),
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
        "released 2026-09-11 today",
        "case ID 2023-45678",
        "PO number 5551234",
        "employee id 4829103",
        "ticket #100234567",
        "build 20260911 shipped",
        "my invoice is INV-2024-0042",
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
