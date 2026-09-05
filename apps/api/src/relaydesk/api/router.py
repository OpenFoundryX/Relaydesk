from fastapi import APIRouter

from relaydesk.api.attachments import router as attachments_router
from relaydesk.api.auth import router as auth_router
from relaydesk.api.channels import router as channels_router
from relaydesk.api.conversations import router as conversations_router
from relaydesk.api.health import router as health_router
from relaydesk.api.kb import router as kb_router
from relaydesk.api.labels import router as labels_router
from relaydesk.api.team import invites_router
from relaydesk.api.team import router as team_router
from relaydesk.api.views import router as views_router
from relaydesk.api.workspace import router as workspace_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(workspace_router, prefix="/workspace", tags=["workspace"])
api_router.include_router(team_router, prefix="/team", tags=["team"])
# Public: acceptance is gated on possession of a token that was mailed to
# the invited address. See relaydesk.api.team.
api_router.include_router(invites_router, prefix="/invites", tags=["team"])
api_router.include_router(conversations_router, prefix="/conversations", tags=["inbox"])
api_router.include_router(labels_router, prefix="/labels", tags=["inbox"])
api_router.include_router(views_router, prefix="/views", tags=["inbox"])
api_router.include_router(channels_router, prefix="/channels", tags=["channels"])
api_router.include_router(
    attachments_router, prefix="/attachments", tags=["attachments"]
)
api_router.include_router(kb_router, prefix="/kb", tags=["knowledge-base"])
