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
