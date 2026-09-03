from pydantic import EmailStr

from relaydesk.schemas.base import CamelModel


class TeamMemberOut(CamelModel):
    id: str
    name: str
    email: str
    role: str
    status: str


class InviteRequest(CamelModel):
    email: EmailStr
    role: str = "Agent"


class InviteCreated(CamelModel):
    id: str
    invite_url: str


class InvitePreview(CamelModel):
    workspace_name: str
    email: str
    role: str


class AcceptInviteRequest(CamelModel):
    name: str
    password: str


class MemberPatch(CamelModel):
    role: str
