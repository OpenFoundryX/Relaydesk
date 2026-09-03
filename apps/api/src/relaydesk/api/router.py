from fastapi import APIRouter

from relaydesk.api.auth import router as auth_router
from relaydesk.api.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
