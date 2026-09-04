from relaydesk.schemas.base import CamelModel


class ChannelOut(CamelModel):
    id: str
    address: str
    display_name: str
    active: bool


class ChannelCreateRequest(CamelModel):
    display_name: str
