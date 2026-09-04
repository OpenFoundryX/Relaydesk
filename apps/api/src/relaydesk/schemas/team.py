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


class AcceptRequest(CamelModel):
    name: str
    password: str


class MemberPatch(CamelModel):
    role: RoleLabel
