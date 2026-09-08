from typing import Literal

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
    #: The one field the console branches on: "duration" formats a Y axis as
    #: `4h 12m`, "count" prints the bare integer. Narrowed to the same union
    #: `MetricSeries` declares in `apps/web/lib/types.ts`, so a typo in
    #: `SERIES_SPEC` fails here instead of shipping a duration card that
    #: renders raw seconds.
    format: Literal["count", "duration"]
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
