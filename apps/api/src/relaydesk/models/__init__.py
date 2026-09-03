"""SQLAlchemy models.

Every model must be imported here so ``Base.metadata`` is complete when
Alembic autogenerates a migration.
"""

from relaydesk.db.base import Base
from relaydesk.models.activity import ActivityEvent, ActivityKind
from relaydesk.models.contact import Contact
from relaydesk.models.conversation import (
    Channel,
    Conversation,
    ConversationLabel,
    ConversationStatus,
    Priority,
    SummaryState,
)
from relaydesk.models.draft import Draft
from relaydesk.models.invite import Invite
from relaydesk.models.label import Label, LabelColor
from relaydesk.models.membership import Membership, MembershipStatus, Role
from relaydesk.models.message import Message, MessageRole
from relaydesk.models.saved_view import SavedView
from relaydesk.models.session import Session
from relaydesk.models.user import User, UserIdentity
from relaydesk.models.workspace import Workspace

__all__ = [
    "ActivityEvent",
    "ActivityKind",
    "Base",
    "Channel",
    "Contact",
    "Conversation",
    "ConversationLabel",
    "ConversationStatus",
    "Draft",
    "Invite",
    "Label",
    "LabelColor",
    "Membership",
    "MembershipStatus",
    "Message",
    "MessageRole",
    "Priority",
    "Role",
    "SavedView",
    "Session",
    "SummaryState",
    "User",
    "UserIdentity",
    "Workspace",
]
