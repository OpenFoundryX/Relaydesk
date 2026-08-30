import logging

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from relaydesk.db.session import engine

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/db")
async def database_health() -> dict[str, str]:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        logger.exception("Database health check failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from error
    return {"status": "ok", "database": "connected"}
