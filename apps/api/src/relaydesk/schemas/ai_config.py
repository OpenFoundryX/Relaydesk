from relaydesk.schemas.base import CamelModel


class AiConfigIn(CamelModel):
    provider: str | None = None
    model: str | None = None
    # Omitted leaves the installed key alone; sending "" clears it.
    api_key: str | None = None
    base_url: str | None = None
    daily_token_budget: int | None = None
    enabled: bool | None = None


class AiConfigOut(CamelModel):
    provider: str
    model: str
    base_url: str | None
    daily_token_budget: int
    enabled: bool
    # The last four characters, so an admin can tell which key is installed
    # without being handed it back. Never the key itself.
    key_suffix: str | None
