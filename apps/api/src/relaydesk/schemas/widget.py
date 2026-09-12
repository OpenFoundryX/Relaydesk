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


class WidgetAskTurn(CamelModel):
    role: str  # "visitor" | "assistant"
    text: str


class WidgetAskIn(CamelModel):
    question: str
    # The client-held transcript, resent each turn -- the server keeps no
    # session (spec D2). Bounded here rather than trusted: an unbounded
    # history is an unbounded bill, on an endpoint anyone can reach.
    history: list[WidgetAskTurn] = Field(default_factory=list, max_length=10)
