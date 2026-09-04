from fastapi import APIRouter

from relaydesk.api.auth import router as auth_router
from relaydesk.api.conversations import router as conversations_router
from relaydesk.api.health import router as health_router
from relaydesk.api.labels import router as labels_router
from relaydesk.api.team import router as team_router
from relaydesk.api.views import router as views_router
from relaydesk.api.workspace import router as workspace_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(workspace_router, prefix="/workspace", tags=["workspace"])
api_router.include_router(team_router, prefix="/team", tags=["team"])
# The public invite router (GET/POST /invites/{token}...) is intentionally
# NOT mounted. See the block comment above the disabled routes in
# relaydesk.api.team for why: an invite binds an email address nobody has
# proved they control, and acceptance issues a session that survives the
# membership being removed. Re-enabling requires acceptance to first prove
# control of the address (e.g. an emailed confirmation link) — do not mount
# this by flipping a config flag.
api_router.include_router(conversations_router, prefix="/conversations", tags=["inbox"])
api_router.include_router(labels_router, prefix="/labels", tags=["inbox"])
api_router.include_router(views_router, prefix="/views", tags=["inbox"])
