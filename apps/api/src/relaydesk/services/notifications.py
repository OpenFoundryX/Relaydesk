from relaydesk.config import get_settings
from relaydesk.models.conversation import Conversation
from relaydesk.models.user import User
from relaydesk.services import queue

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
