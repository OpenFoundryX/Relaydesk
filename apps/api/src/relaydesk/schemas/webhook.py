from datetime import datetime
from typing import Literal

from pydantic import Field

from relaydesk.models import WebhookMethod
from relaydesk.schemas.base import CamelModel


class WebhookParamIn(CamelModel):
    """One declared argument.

    The closed set of types lives here rather than in a database constraint:
    ``params`` is JSONB (spec D5), so this is the edge that enforces it.
    """

    name: str = Field(min_length=1, max_length=64)
    type: Literal["string", "number", "boolean"] = "string"
    description: str = Field(default="", max_length=200)
    required: bool = False


class WebhookOut(CamelModel):
    """What the settings list shows. Never the secret."""

    id: str
    name: str
    description: str
    method: WebhookMethod
    url: str
    params: list[WebhookParamIn]
    created_at: datetime


class WebhookCreate(CamelModel):
    name: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=500)
    method: WebhookMethod
    url: str = Field(min_length=1, max_length=2048)
    params: list[WebhookParamIn] = Field(default_factory=list)


class WebhookUpdate(CamelModel):
    """Every field optional: what is absent is left alone.

    An empty ``params`` list clears the parameters, which is why the default
    is ``None`` rather than ``[]`` -- the two have to mean different things.
    """

    name: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = Field(default=None, min_length=1, max_length=500)
    method: WebhookMethod | None = None
    url: str | None = Field(default=None, min_length=1, max_length=2048)
    params: list[WebhookParamIn] | None = None


class WebhookCreated(CamelModel):
    """The only response shape that carries the signing secret.

    Unlike an API key's token, this one *is* recoverable -- by rotating it,
    which mints a new one. It is not shown in the list because a value that
    appears on every page render is a value that ends up in a screenshot.
    """

    webhook: WebhookOut
    secret: str


class WebhookTestRequest(CamelModel):
    arguments: dict[str, object] = Field(default_factory=dict)


class WebhookTestResult(CamelModel):
    """What came back from the receiver, or why nothing did."""

    ok: bool
    status: int | None
    duration_ms: int
    response_body: str
    error: str | None
