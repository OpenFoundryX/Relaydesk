from relaydesk.config import get_settings
from relaydesk.models.conversation import Conversation
from relaydesk.models.user import User
from relaydesk.services import queue
from relaydesk.services.team import INVITE_TTL

ASSIGNMENT_TEXT = """\
{actor} assigned a conversation to you.

{subject}
From {customer}

Open it: {url}
"""


def notify_assignment(
    conversation: Conversation, assignee: User, actor: User
) -> None:
    """Fire-and-forget. Never raises into the caller's request: an email that
    fails to enqueue must not fail the assignment itself."""
    if assignee.id == actor.id or not assignee.notify_on_assignment:
        return

    customer = conversation.contact.name if conversation.contact else "a customer"
    url = f"{get_settings().web_url}/conversations/{conversation.id}"
    queue.enqueue_system_email(
        to=assignee.email,
        subject=f"Assigned to you: {conversation.subject}",
        text_body=ASSIGNMENT_TEXT.format(
            actor=actor.name,
            subject=conversation.subject,
            customer=customer,
            url=url,
        ),
    )


INVITE_TEXT = """\
{inviter} invited you to join {workspace} on Relaydesk.

Accept the invitation: {url}

This link expires in {ttl_days} days. If you weren't expecting it, ignore
this message — no account is created until you accept.
"""


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
    queue.enqueue_system_email(
        to=email,
        subject=f"Join {workspace_name} on Relaydesk",
        text_body=INVITE_TEXT.format(
            inviter=inviter_name,
            workspace=workspace_name,
            url=url,
            ttl_days=INVITE_TTL.days,
        ),
    )
