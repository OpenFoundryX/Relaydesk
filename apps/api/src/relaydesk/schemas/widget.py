from typing import Literal

from pydantic import Field, field_validator

from relaydesk.schemas.base import CamelModel


class WidgetBootstrapOut(CamelModel):
    workspace_name: str
    # The workspace's own subdomain on the public help site. The panel has
    # no session to resolve one from -- it is anonymous, addressed only by
    # a key -- so "open this in the help centre" had nowhere to point and
    # linked to a path on the widget's own origin, which resolves to no
    # workspace and 404s. The slug is the address of every article the
    # workspace has published and does not change when it is renamed.
    workspace_slug: str
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
        """Reduce a conversation to a shape the provider will accept, and
        bound what it costs.

        The Messages API has three structural rules, and each is a 400
        rather than a tolerated shape: the first message must be `user`,
        roles must strictly alternate, and no content block may be empty.
        `AnthropicProvider.complete` turns a 400 into a provider error and
        `ai_budget.breaker_open` counts those -- so an unaccepted shape did
        not merely fail one question, it disabled AI for the whole
        workspace once five arrived in fifteen minutes.

        That cannot be left to the caller. The key sits in any customer's
        page source, so a hostile caller can send whatever it likes; and
        the bundled client is not well-behaved either -- it appends the
        escalation offer directly after an answer, which is two assistant
        turns in a row, so an ordinary fourth question carried a guaranteed
        400 of its own.

        Order matters. Blank turns go first, because a turn that is only
        whitespace should not keep two real turns apart. Then same-role
        runs are merged rather than dropped, which preserves what was said
        and makes the sequence alternate. Only then is each turn clipped
        and the window taken -- merging afterwards could re-introduce a
        run, and taking the window first could slice a merged conversation
        back into a non-alternating one.

        The two ends are trimmed last. A leading assistant turn is the
        greeting bubble every conversation opens with, and it has nothing
        before it to answer. A trailing visitor turn goes because
        `question` is appended after all of these as the next user turn,
        and two user turns together is the same 400 from the other side.

        Truncation throughout, never rejection: a visitor must not be
        blocked by the shape or the length of their own conversation --
        the principle `QUESTION_MAX_CHARS` and `TRANSCRIPT_MAX_CHARS`
        already apply to the other two visitor-controlled fields here. The
        oldest turns are the safest to drop, for the reason
        `TRANSCRIPT_MAX_CHARS` gives below: what a visitor asked a moment
        ago is what "that" refers to, not what they asked six turns back.
        """
        spoken = [turn for turn in turns if turn.text.strip()]

        merged: list[WidgetTurnIn] = []
        for turn in spoken:
            if merged and merged[-1].role == turn.role:
                merged[-1] = merged[-1].model_copy(
                    update={"text": f"{merged[-1].text}\n\n{turn.text}"}
                )
            else:
                merged.append(turn)

        clipped = [
            turn
            if len(turn.text) <= HISTORY_TURN_MAX_CHARS
            else turn.model_copy(update={"text": turn.text[:HISTORY_TURN_MAX_CHARS]})
            for turn in merged
        ]

        window = clipped[-HISTORY_MAX_TURNS:]
        if window and window[0].role == "assistant":
            window = window[1:]
        if window and window[-1].role == "visitor":
            window = window[:-1]
        return window


# The ticket route's `transcript` field is truncated to this many
# characters, not rejected: a visitor escalating to a human because the AI
# could not help must never be blocked by the length of their own
# conversation (spec D8). Truncated from the front, keeping the tail --
# the exchange immediately before escalation is what the agent most needs
# to see, and the oldest turns are the safest ones to drop first.
TRANSCRIPT_MAX_CHARS = 4000
