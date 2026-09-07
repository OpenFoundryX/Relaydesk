from datetime import datetime
from typing import Annotated

from pydantic import EmailStr, Field

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
    notify_on_assignment: bool


class WorkspaceOut(CamelModel):
    id: str
    name: str
    #: The subdomain label the workspace is reached at. Not decoration: the
    #: public help site lives at ``<slug>.<portal domain>``, so the console
    #: cannot link a member to their own published article without it.
    slug: str
    monogram: str
    seats: int


class MembershipOut(CamelModel):
    role: str


class MeResponse(CamelModel):
    user: UserOut
    workspace: WorkspaceOut
    membership: MembershipOut


class MePatch(CamelModel):
    # User.name is String(120); without this bound an over-length rename
    # reached the database and raised StringDataRightTruncation (a 500)
    # instead of a 422.
    name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    notify_on_assignment: bool | None = None


class PasswordResetRequest(CamelModel):
    email: EmailStr


class PasswordResetConfirm(CamelModel):
    token: str
    # The same minimum as accepting an invite (`schemas.team`), which is the
    # only other way a password is ever set. Stated by reference rather than
    # by a second literal so the two cannot drift apart.
    password: Annotated[str, Field(min_length=8)]
