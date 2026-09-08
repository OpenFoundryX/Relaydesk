from pydantic import Field, field_validator

from relaydesk.schemas.base import CamelModel


class SetupTaskOut(CamelModel):
    id: str
    label: str
    href: str
    done: bool


class WorkspacePatch(CamelModel):
    name: str | None = None
    timezone: str | None = None
    #: The initials on the tile beside the workspace name, in the console
    #: header and on the help centre's hero.
    monogram: str | None = Field(default=None, max_length=4)

    @field_validator("monogram")
    @classmethod
    def _reject_blank(cls, value: str | None) -> str | None:
        """`max_length` counts characters, so "   " passes it and the tile
        then renders as a coloured square with nothing in it -- on every
        page, for everyone. Rejected at the boundary rather than left to
        whatever the service happens to do with the value."""
        if value is not None and not value.strip():
            raise ValueError("A monogram cannot be blank.")
        return value
