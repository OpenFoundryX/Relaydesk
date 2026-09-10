import uuid
from datetime import datetime

from pydantic import Field

from relaydesk.schemas.base import CamelModel


class WidgetKeyCreate(CamelModel):
    name: str = Field(min_length=1, max_length=120)
    allowed_origins: list[str] = Field(default_factory=list)
    settings: dict = Field(default_factory=dict)


class WidgetKeyUpdate(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    allowed_origins: list[str] | None = None
    settings: dict | None = None
    active: bool | None = None


class WidgetKeyOut(CamelModel):
    id: uuid.UUID
    name: str
    # Returned in full on every read, unlike ApiKey's one-time secret: this
    # value is published in page source and the admin needs it to re-paste.
    key: str
    allowed_origins: list[str]
    settings: dict
    active: bool
    last_seen_at: datetime | None
    created_at: datetime
