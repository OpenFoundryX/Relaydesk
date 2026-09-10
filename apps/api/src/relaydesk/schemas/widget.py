from relaydesk.schemas.base import CamelModel


class WidgetBootstrapOut(CamelModel):
    workspace_name: str
    monogram: str
    settings: dict
    # Drives the empty-knowledge-base screen (spec D7).
    article_count: int
