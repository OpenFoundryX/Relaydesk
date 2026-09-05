from relaydesk.services.kb_text import derive_excerpt, extract_text, slugify


def _doc(*content: dict) -> dict:
    return {"type": "doc", "content": list(content)}


def _para(text: str) -> dict:
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def test_text_is_extracted_in_document_order() -> None:
    doc = _doc(_para("First."), _para("Second."))

    assert extract_text(doc) == "First. Second."


def test_nested_content_is_reached() -> None:
    """Lists nest two levels deep, and a flat walk would miss the text."""
    doc = _doc(
        {
            "type": "bulletList",
            "content": [
                {"type": "listItem", "content": [_para("Alpha")]},
                {"type": "listItem", "content": [_para("Beta")]},
            ],
        }
    )

    assert extract_text(doc) == "Alpha Beta"


def test_an_unknown_node_type_does_not_stop_extraction() -> None:
    """A document written by a newer editor must still yield its text."""
    doc = _doc(
        _para("Before"),
        {"type": "somethingNew", "content": [_para("Inside")]},
        _para("After"),
    )

    assert extract_text(doc) == "Before Inside After"


def test_a_document_with_no_text_yields_an_empty_string() -> None:
    doc = _doc({"type": "horizontalRule"})

    assert extract_text(doc) == ""


def test_a_malformed_document_does_not_raise() -> None:
    """This runs on whatever the editor posts. Raising here would fail a save
    the author cannot diagnose."""
    assert extract_text({}) == ""
    assert extract_text({"type": "doc", "content": "not a list"}) == ""
    assert extract_text({"type": "doc", "content": [None, 42, "text"]}) == ""


def test_slugify_lowercases_and_hyphenates() -> None:
    assert slugify("Handling a Refund Request") == "handling-a-refund-request"


def test_slugify_strips_punctuation_and_collapses_separators() -> None:
    assert slugify("What's new?  (2026 edition)") == "whats-new-2026-edition"


def test_slugify_never_returns_an_empty_string() -> None:
    """An empty slug would produce an unreachable URL, so it falls back."""
    assert slugify("") == "untitled"
    assert slugify("!!!") == "untitled"
    assert slugify("   ") == "untitled"


def test_slugify_bounds_its_output() -> None:
    assert len(slugify("word " * 100)) <= 200


def test_slugify_preserves_literal_hyphens() -> None:
    """Literal hyphens in titles are preserved as word separators."""
    assert slugify("Step-by-step guide") == "step-by-step-guide"


def test_slugify_handles_accented_characters() -> None:
    """Accented characters are normalized to ASCII equivalents via NFKD."""
    assert slugify("Café basics") == "cafe-basics"


def test_derive_excerpt_truncates_on_a_word_boundary() -> None:
    text = "Refunds are issued within thirty days of the original charge date."

    assert derive_excerpt(text, limit=30) == "Refunds are issued within…"


def test_derive_excerpt_leaves_short_text_alone() -> None:
    assert derive_excerpt("Short.", limit=200) == "Short."
