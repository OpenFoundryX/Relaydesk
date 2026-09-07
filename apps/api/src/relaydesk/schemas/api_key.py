from datetime import datetime

from pydantic import Field

from relaydesk.models import ApiKeyScope
from relaydesk.schemas.base import CamelModel


class ApiKeyOut(CamelModel):
    """What the settings list shows. Never the secret.

    ``CamelModel``, unlike everything in ``schemas.v1``: this is the
    console's own surface and matches its TypeScript types field for field.
    """

    id: str
    name: str
    prefix: str
    scopes: list[str]
    created_at: datetime
    last_used_at: datetime | None


class ApiKeyCreate(CamelModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: list[ApiKeyScope] = Field(min_length=1)


class ApiKeyCreated(CamelModel):
    """The one response that carries the plaintext token.

    It is not recoverable afterwards -- only the SHA-256 digest is stored --
    which is why the dialog says the key is shown once and why rotation is
    "create a new one, delete the old one" rather than a reveal.
    """

    token: str
    key: ApiKeyOut
