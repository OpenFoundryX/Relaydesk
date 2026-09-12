from pydantic import Field

from relaydesk.schemas.base import CamelModel


class WidgetBootstrapOut(CamelModel):
    workspace_name: str
    monogram: str
    settings: dict
    # Drives the empty-knowledge-base screen (spec D7).
    article_count: int


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


class WidgetAskIn(CamelModel):
    question: str = Field(max_length=QUESTION_MAX_CHARS)
    # No client-held transcript field: an earlier draft carried one, but
    # nothing in this slice reads it -- the panel (Task 10) sends only the
    # question, and escalation (Task 11) carries prior turns as a separate
    # `transcript` form field on the ticket route instead. A field neither
    # produced nor consumed anywhere is worse than no field: it invites a
    # caller to rely on context that is silently dropped.
