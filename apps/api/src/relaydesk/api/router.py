from fastapi import APIRouter

from relaydesk.api.auth import router as auth_router
from relaydesk.api.conversations import router as conversations_router
from relaydesk.api.health import router as health_router
from relaydesk.api.labels import router as labels_router
from relaydesk.api.team import invite_router
from relaydesk.api.team import router as team_router
from relaydesk.api.views import router as views_router
from relaydesk.api.workspace import router as workspace_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(workspace_router, prefix="/workspace", tags=["workspace"])
api_router.include_router(team_router, prefix="/team", tags=["team"])
api_router.include_router(invite_router, prefix="/invites", tags=["team"])
api_router.include_router(conversations_router, prefix="/conversations", tags=["inbox"])
api_router.include_router(labels_router, prefix="/labels", tags=["inbox"])
api_router.include_router(views_router, prefix="/views", tags=["inbox"])
