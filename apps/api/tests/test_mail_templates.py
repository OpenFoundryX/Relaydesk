from relaydesk.services import mail_templates, notifications
from relaydesk.services.actors import Actor
from tests.factories import make_conversation, make_member, make_workspace


def test_the_text_part_carries_the_paragraphs_and_the_action() -> None:
    text, _ = mail_templates.render(
        heading="Reset your password",
        paragraphs=["Somebody asked to reset it.", "The link expires in 60 minutes."],
        action_label="Choose a new password",
        action_url="http://localhost:3000/reset-password#abc",
    )

    assert "Somebody asked to reset it." in text
    assert "The link expires in 60 minutes." in text
    assert "Choose a new password: http://localhost:3000/reset-password#abc" in text
    # The heading is an HTML affordance; the subject line is the text
    # part's heading, so repeating it here would just read as a stutter.
    assert "Reset your password" not in text
    assert "<p" not in text


def test_the_html_part_shows_the_url_as_text_as_well_as_a_link() -> None:
    """A client that strips links must still leave the user a usable URL."""
    _, html = mail_templates.render(
        heading="Reset your password",
        paragraphs=["Somebody asked to reset it."],
        action_label="Choose a new password",
        action_url="http://localhost:3000/reset-password#abc",
    )

    assert 'href="http://localhost:3000/reset-password#abc"' in html
    assert html.count("http://localhost:3000/reset-password#abc") >= 2
    assert "<h1" in html
    assert "Reset your password" in html


def test_the_html_part_escapes_its_content() -> None:
    _, html = mail_templates.render(
        heading="Join Ben & Co",
        paragraphs=["<script>alert(1)</script> invited you."],
    )

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "Ben &amp; Co" in html


def test_the_html_part_pulls_in_nothing_from_the_network() -> None:
    """No remote images, no web fonts, no tracking pixel: a mail client that
    blocks remote content must render this identically, and Relaydesk must
    not learn whether a reset mail was opened."""
    _, html = mail_templates.render(
        heading="Reset your password",
        paragraphs=["Somebody asked to reset it."],
        action_label="Choose a new password",
        action_url="http://localhost:3000/reset-password#abc",
    )

    assert "<img" not in html
    assert "<style" not in html
    assert "@import" not in html
    assert "url(" not in html


def test_an_action_is_optional() -> None:
    text, html = mail_templates.render(
        heading="Assigned to you",
        paragraphs=["Nilesh assigned a conversation to you."],
    )

    assert "Nilesh assigned a conversation to you." in text
    assert "<a " not in html


def test_an_invite_email_has_both_parts(outbox) -> None:
    notifications.notify_invite(
        email="sara@example.com",
        token="tok",
        workspace_name="Chronon",
        inviter_name="Nilesh Pant",
    )

    assert len(outbox) == 1
    assert "Nilesh Pant invited you to join Chronon" in outbox[0]["text"]
    # Still a fragment, still not a path segment.
    assert "/invites#tok" in outbox[0]["text"]
    assert "/invites/tok" not in outbox[0]["text"]
    assert outbox[0]["html"] is not None
    assert "/invites#tok" in outbox[0]["html"]


async def test_an_assignment_email_has_both_parts(db_session, outbox) -> None:
    workspace = await make_workspace(db_session)
    actor = await make_member(db_session, workspace, email="nilesh@example.com")
    assignee = await make_member(
        db_session, workspace, email="sara@example.com", name="Sara Vidal"
    )
    conversation = await make_conversation(db_session, workspace)
    await db_session.refresh(conversation, ["contact"])

    notifications.notify_assignment(conversation, assignee, Actor.for_user(actor))

    assert len(outbox) == 1
    assert outbox[0]["to"] == "sara@example.com"
    assert outbox[0]["html"] is not None
    assert "<h1" in outbox[0]["html"]
