import enum
import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class WebhookMethod(enum.StrEnum):
    """The values are the HTTP method verbatim.

    They go on the wire as the method, into the signed payload, and into the
    console's badge, so there is no case-mapping layer anywhere to keep in
    step with this enum.
    """

    get = "GET"
    post = "POST"
    put = "PUT"
    patch = "PATCH"
    delete = "DELETE"


class Webhook(UUIDMixin, TimestampMixin, Base):
    """An endpoint a workspace owns, registered as a tool Relaydesk can call.

    Not an event subscription. Nothing here fires because something happened
    in the inbox; something inside Relaydesk decides to call this endpoint to
    get a job done, with arguments. The distinction is load-bearing and is
    spec D1: redelivering an event is harmless, and calling ``refund_order``
    twice is a second refund, so the two cannot share a table that has to
    settle whether a retry is safe.

    ``secret`` is stored in plaintext, which departs from every other
    credential in this schema. ``ApiKey`` keeps only a SHA-256 digest, and
    ``ChannelAccount`` deliberately holds no credentials at all so that a
    database compromise grants no mailbox access. A signature the receiver
    can verify needs the same key at both ends, so this table cannot make
    either promise: **a database compromise discloses every webhook secret,
    and with it the ability to forge requests to the endpoints that trust
    them.** Spec D2 records what was weighed against that -- encryption at
    rest was rejected for the required-key-in-every-deployment cost, and is
    the thing to revisit if a secrets manager ever enters this stack. What
    ships instead is a secret per webhook rather than per workspace, so a
    leak is scoped to one integration, and rotation as a first-class
    operation rather than delete-and-recreate.

    ``description`` is not decoration and is not nullable. It is the text a
    tool-selecting agent reads to decide whether this is the right endpoint
    for a job, which is why the console's own copy tells admins to write
    them carefully.

    ``name`` is an identifier, unique per workspace: a tool is chosen by
    name, and two ``refund_order``s in one workspace is an ambiguity with no
    correct resolution. Uniqueness stops at the workspace boundary -- one
    tenant's naming has no business constraining another's.

    ``created_by_user_id`` is SET NULL for ``ApiKey``'s reason: the webhook
    belongs to the workspace and has to outlive whoever registered it.

    Deletion is a real delete, unlike ``ApiKey``'s ``revoked_at`` tombstone.
    A key is kept because ``activity_events.actor_api_key_id`` must go on
    resolving to a name; nothing references a webhook, so there is no
    attribution to preserve.
    """

    __tablename__ = "webhooks"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_webhooks_workspace_name"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    method: Mapped[WebhookMethod] = mapped_column(
        SAEnum(
            WebhookMethod,
            name="ck_webhooks_method",
            native_enum=False,
            length=8,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    # JSONB rather than a child table (spec D5): parameters are read and
    # written as a unit, never queried across webhooks, and a child table
    # would buy referential tidiness at the cost of a join on every read and
    # an ordering column to preserve the sequence the dialog shows. The
    # closed set of types is enforced at the Pydantic edge.
    params: Mapped[list[dict]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    secret: Mapped[str] = mapped_column(String(70), nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
