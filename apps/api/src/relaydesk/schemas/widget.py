from typing import Literal

from pydantic import Field, field_validator

from relaydesk.schemas.base import CamelModel


class WidgetBootstrapOut(CamelModel):
    workspace_name: str
    monogram: str
    settings: dict
    # Drives the empty-knowledge-base screen (spec D7).
    article_count: int
    # Whether this workspace can actually answer questions -- `enabled` AND a
    # key installed, the same pair `ai_provider.for_config` requires. The
    # panel opens on the conversation view only when this is true; without
    # it every visitor would be shown a question box that could never answer,
    # and would bounce them to search after typing. Deliberately a bare boolean:
    # which provider, which model and what it costs are nobody's business
    # outside the console.
    ai_enabled: bool = False


class WidgetEventIn(CamelModel):
    """ "searched", "read" or "submitted". Checked against that closed set
    in `widget_sessions.record`, not here with an enum -- a stray value is
    still refused, just by the same `Invalid` every other domain rule uses."""

    kind: str


# A generous multiple of any real support question -- most are a sentence
# or two -- and small next to `ticket_message_max_chars` (10,000, a whole
# ticket description). This is the one field that is actually embedded in
# the model prompt and billed per call (`ai_answers.answer`), on an
# anonymous route whose key sits in any customer's page source, so it is
# the single most direct lever on cost per request. `ai_budget.within_budget`
# only bounds *cumulative* spend before a call starts; nothing bounds what
# one call can cost without this.
QUESTION_MAX_CHARS = 2000


# A prior draft carried a `history` field on `WidgetAskIn` and removed it as
# dead input -- nothing consumed it, and escalation (Task 11) carries prior
# turns as a separate `transcript` form field on the ticket route instead.
# This is its real introduction: Task 10's follow-up questions ("what about
# annually?") are unanswerable without the turn they follow, so the model
# now receives this as real conversation, not just the ticket route.
HISTORY_MAX_TURNS = 6
HISTORY_TURN_MAX_CHARS = 1000


class WidgetTurnIn(CamelModel):
    """One prior turn of this browser session's conversation, as the
    visitor's browser remembers it and resends on every question.

    Visitor-supplied and unverified: a visitor's own browser is what wrote
    even the "assistant" turns here, so nothing in this shape is proof that
    an assistant ever said it. See `ai_answers.SYSTEM` for how the model is
    told to treat it.
    """

    role: Literal["visitor", "assistant"]
    text: str


class WidgetAskIn(CamelModel):
    question: str = Field(max_length=QUESTION_MAX_CHARS)
    # Prior turns of this session, oldest first. Bounded below rather than
    # rejected: this is both a cost surface (every turn is billed, on every
    # question, for the life of the conversation) and an abuse surface (an
    # anonymous route whose key sits in any customer's page source), but a
    # visitor must never be blocked by the length of their own conversation
    # -- the same principle `QUESTION_MAX_CHARS` and `TRANSCRIPT_MAX_CHARS`
    # already apply to the two other visitor-controlled text fields on this
    # door. `_bound_history` truncates; nothing here raises 422 for it.
    history: list[WidgetTurnIn] = Field(default_factory=list)

    @field_validator("history", mode="after")
    @classmethod
    def _bound_history(cls, turns: list[WidgetTurnIn]) -> list[WidgetTurnIn]:
        """Keep at most the last `HISTORY_MAX_TURNS` turns, oldest dropped
        first, each clipped to `HISTORY_TURN_MAX_CHARS`.

        The oldest turns are the safest to drop -- the same reasoning
        `TRANSCRIPT_MAX_CHARS`'s truncation-from-the-front uses below, and
        for the same reason: what a visitor asked a moment ago is what
        "that" in a follow-up question refers to, not what they asked six
        turns back.
        """
        kept = turns[-HISTORY_MAX_TURNS:]
        return [
            turn
            if len(turn.text) <= HISTORY_TURN_MAX_CHARS
            else turn.model_copy(update={"text": turn.text[:HISTORY_TURN_MAX_CHARS]})
            for turn in kept
        ]


# The ticket route's `transcript` field is truncated to this many
# characters, not rejected: a visitor escalating to a human because the AI
# could not help must never be blocked by the length of their own
# conversation (spec D8). Truncated from the front, keeping the tail --
# the exchange immediately before escalation is what the agent most needs
# to see, and the oldest turns are the safest ones to drop first.
TRANSCRIPT_MAX_CHARS = 4000
