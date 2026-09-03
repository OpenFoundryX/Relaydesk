from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from relaydesk import __version__
from relaydesk.api.router import api_router
from relaydesk.config import get_settings
from relaydesk.errors import AppError

settings = get_settings()

app = FastAPI(title="Relaydesk API", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")


@app.exception_handler(AppError)
async def handle_app_error(_: Request, error: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={"error": {"code": error.code, "message": error.message}},
    )


@app.get("/")
async def api_info() -> dict[str, str]:
    return {"name": "Relaydesk API", "version": __version__}
