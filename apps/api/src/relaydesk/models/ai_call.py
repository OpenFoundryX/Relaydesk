import enum
import uuid

from sqlalchemy import BigInteger, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class AiOutcome(enum.StrEnum):
    """What happened, in the terms the deflection number is computed in."""

    answered = "answered"
    escalated = "escalated"
    refused = "refused"
    degraded = "degraded"


class AiCall(UUIDMixin, TimestampMixin, Base):
    """One inference attempt, recorded whatever became of it.

    This table is what makes a deflection figure auditable rather than
    asserted. A vendor's published resolution rate is a claim; a workspace
    that can run a query over its own calls has a number.

    It holds no message content -- not the question, not the answer, not the
    retrieved articles. The transcript lives in the visitor's browser for
    the life of the panel and, on escalation only, in the ticket they chose
    to send. What is recorded here is shape and cost, never what was said.

    ``cost_micros`` is an integer count of millionths of a unit of currency.
    Money in a float is a rounding argument waiting to happen, and this
    column will eventually be summed across a billing period.

    ``widget_key_id`` is ``SET NULL`` rather than cascade on purpose:
    deleting an embed is how it is revoked (see ``WidgetKey``), and
    revocation must not erase the record of what that embed spent.
    """

    __tablename__ = "ai_calls"
    __table_args__ = (Index("ix_ai_calls_workspace_created", "workspace_id", "created_at"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    widget_key_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("widget_keys.id", ondelete="SET NULL"),
        nullable=True,
    )
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_micros: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outcome: Mapped[AiOutcome] = mapped_column(
        Enum(
            AiOutcome,
            name="ck_ai_calls_outcome",
            native_enum=False,
            length=16,
            create_constraint=True,
        ),
        nullable=False,
    )
    # More detail on `outcome`: which of spec D4's conditions applied when
    # `outcome` is `degraded` (e.g. "not_configured", "over_budget",
    # "breaker_open", "provider_unavailable", or "incomplete" for a charge
    # that never got the chance to settle), or why the model produced
    # nothing citable when `outcome` is `refused` ("no_citation" for a
    # grounded answer that cited nothing, "declined" for a genuine model
    # refusal, "clarify" for a clarify-only turn -- the model was called
    # with no retrieved sources and asked a question back rather than
    # answering; the wire layer renders this as "clarified", but it is not
    # a fourth `AiOutcome` value). `provider_unavailable` is reserved for
    # real provider failures -- `ai_budget.breaker_open` counts only that
    # value, so a refusal must never be filed under it.
    reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
