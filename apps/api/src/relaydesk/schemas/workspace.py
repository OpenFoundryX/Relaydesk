from relaydesk.schemas.base import CamelModel


class SetupTaskOut(CamelModel):
    id: str
    label: str
    href: str
    done: bool


class WorkspacePatch(CamelModel):
    name: str | None = None
    timezone: str | None = None
