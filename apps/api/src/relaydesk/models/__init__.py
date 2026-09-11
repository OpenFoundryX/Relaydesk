"""SQLAlchemy models.

Every model must be imported here so ``Base.metadata`` is complete when
Alembic autogenerates a migration.
"""

from relaydesk.db.base import Base
from relaydesk.models.activity import ActivityEvent, ActivityKind
from relaydesk.models.ai_config import AiConfig
from relaydesk.models.api_key import ApiKey, ApiKeyScope
from relaydesk.models.api_usage import ApiKeyUsage
from relaydesk.models.attachment import Attachment
from relaydesk.models.channel_account import ChannelAccount, ChannelAccountKind
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
from relaydesk.models.kb import ArticleStatus, KbArticle, KbCategory, KbImage, KbScope
from relaydesk.models.label import Label, LabelColor
from relaydesk.models.membership import Membership, MembershipStatus, Role
from relaydesk.models.message import (
    DeliveryState,
    Message,
    MessageDirection,
    MessageRole,
)
from relaydesk.models.password_reset import PasswordReset
from relaydesk.models.poll_state import PollState
from relaydesk.models.rate_limit import RateLimitHit
from relaydesk.models.raw_message import RawMessage, RawMessageState
from relaydesk.models.session import Session
from relaydesk.models.snippet import Snippet
from relaydesk.models.user import User, UserIdentity
from relaydesk.models.webhook import Webhook, WebhookMethod
from relaydesk.models.widget_key import WidgetKey
from relaydesk.models.widget_session import WidgetSession
from relaydesk.models.workspace import Workspace

__all__ = [
    "ActivityEvent",
    "ActivityKind",
    "AiConfig",
    "ApiKey",
    "ApiKeyScope",
    "ApiKeyUsage",
    "ArticleStatus",
    "Attachment",
    "Base",
    "Channel",
    "ChannelAccount",
    "ChannelAccountKind",
    "Contact",
    "Conversation",
    "ConversationLabel",
    "ConversationStatus",
    "DeliveryState",
    "Draft",
    "Invite",
    "KbArticle",
    "KbCategory",
    "KbImage",
    "KbScope",
    "Label",
    "LabelColor",
    "Membership",
    "MembershipStatus",
    "Message",
    "MessageDirection",
    "MessageRole",
    "PasswordReset",
    "PollState",
    "Priority",
    "RateLimitHit",
    "RawMessage",
    "RawMessageState",
    "Role",
    "Session",
    "Snippet",
    "SummaryState",
    "User",
    "UserIdentity",
    "Webhook",
    "WebhookMethod",
    "WidgetKey",
    "WidgetSession",
    "Workspace",
]
