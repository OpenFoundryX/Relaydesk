from relaydesk.schemas.base import CamelModel


class MetricPointOut(CamelModel):
    date: str
    value: float


class MetricSeriesOut(CamelModel):
    id: str
    label: str
    hint: str | None = None
    #: Preformatted by the API ("412", "8m 24s"). The console prints it
    #: verbatim; `format` drives the axis, not this.
    headline: str
    delta: int | None
    format: str
    points: list[MetricPointOut]


class AgentRowOut(CamelModel):
    user_id: str
    name: str
    handled: int
    first_response_seconds: float | None
    resolved: int


class AnalyticsOut(CamelModel):
    series: list[MetricSeriesOut]
    agents: list[AgentRowOut]
