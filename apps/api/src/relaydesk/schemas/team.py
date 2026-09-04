from typing import Literal

from pydantic import EmailStr

from relaydesk.schemas.base import CamelModel

# The wire vocabulary for a role is the label the console shows and
# /auth/me returns for a membership. Typing it rather than taking a bare
# ``str`` means "admin" (or anything else) is a 422 instead of quietly
# falling through to Agent and demoting somebody.
RoleLabel = Literal["Admin", "Agent"]


class TeamMemberOut(CamelModel):
    id: str
    name: str
    email: str
    role: str
    status: str
    user_id: str | None


class InviteRequest(CamelModel):
    email: EmailStr
    role: RoleLabel = "Agent"


class InvitePreview(CamelModel):
    workspace_name: str
    email: str
    role: str


class TokenRequest(CamelModel):
    """The invite token in a request body, never a path segment.

    A path segment lands verbatim in the access log on every request; a
    body field does not. See the block comment on the invite routes in
    ``relaydesk.api.team``.
    """

    token: str


class AcceptRequest(CamelModel):
    token: str
    name: str
    password: str


class MemberPatch(CamelModel):
    role: RoleLabel
