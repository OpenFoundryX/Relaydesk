from relaydesk.config import get_settings
from relaydesk.models.conversation import Conversation
from relaydesk.models.user import User
from relaydesk.services import mail_templates, queue
from relaydesk.services.team import INVITE_TTL


def notify_assignment(
    conversation: Conversation, assignee: User, actor: User
) -> None:
    """Fire-and-forget. Never raises into the caller's request: an email that
    fails to enqueue must not fail the assignment itself."""
    if assignee.id == actor.id or not assignee.notify_on_assignment:
        return

    customer = conversation.contact.name if conversation.contact else "a customer"
    url = f"{get_settings().web_url}/conversations/{conversation.id}"
    text, html = mail_templates.render(
        heading="Assigned to you",
        paragraphs=[
            f"{actor.name} assigned a conversation to you.",
            f"{conversation.subject}\nFrom {customer}",
        ],
        action_label="Open it",
        action_url=url,
    )
    queue.enqueue_system_email(
        to=assignee.email,
        subject=f"Assigned to you: {conversation.subject}",
        text_body=text,
        html_body=html,
    )


def notify_invite(
    email: str, token: str, workspace_name: str, inviter_name: str
) -> None:
    """The token is delivered here and nowhere else — never in a response
    body, never in a log line.

    The token goes in the URL *fragment* (``#token``), not a path segment or
    query string: a fragment is never sent to any server, including the web
    app's own, so it never reaches an access log. ``/invites/{token}`` as a
    path segment was the mistake this replaces — see the block comment on
    the invite routes in ``relaydesk.api.team``.
    """
    url = f"{get_settings().web_url}/invites#{token}"
    text, html = mail_templates.render(
        heading=f"Join {workspace_name}",
        paragraphs=[
            f"{inviter_name} invited you to join {workspace_name} on Relaydesk.",
            f"This link expires in {INVITE_TTL.days} days. If you weren't "
            "expecting it, ignore this message — no account is created until "
            "you accept.",
        ],
        action_label="Accept the invitation",
        action_url=url,
    )
    queue.enqueue_system_email(
        to=email,
        subject=f"Join {workspace_name} on Relaydesk",
        text_body=text,
        html_body=html,
    )
