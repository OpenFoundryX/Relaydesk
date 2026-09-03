from datetime import datetime

from pydantic import EmailStr

from relaydesk.schemas.base import CamelModel


class LoginRequest(CamelModel):
    email: EmailStr
    password: str


class TokenResponse(CamelModel):
    token: str
    expires_at: datetime


class GoogleUrlResponse(CamelModel):
    url: str
    state: str


class GoogleExchangeRequest(CamelModel):
    code: str
    redirect_uri: str


class UserOut(CamelModel):
    id: str
    name: str
    email: str
    monogram: str
    time_zone: str


class WorkspaceOut(CamelModel):
    id: str
    name: str
    monogram: str
    plan: str
    trial_days_left: int
    seats: int
    tickets_this_period: int
    projected_tickets: int


class MembershipOut(CamelModel):
    role: str


class MeResponse(CamelModel):
    user: UserOut
    workspace: WorkspaceOut
    membership: MembershipOut
