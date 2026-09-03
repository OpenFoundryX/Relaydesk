from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

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


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    _: Request, error: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {"code": "invalid", "message": "Request payload is invalid."}
        },
    )


# Status codes that already carry a matching AppError subclass keep that
# subclass's code, so a framework-raised HTTPException (an unmatched route,
# or a bare `raise HTTPException(...)`) reads identically to a domain error
# at the same status — including the 404 the cross-workspace-isolation
# contract in later tasks relies on.
_HTTP_EXCEPTION_CODES = {
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "invalid",
}


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(
    _: Request, error: StarletteHTTPException
) -> JSONResponse:
    code = _HTTP_EXCEPTION_CODES.get(error.status_code, "error")
    message = error.detail if isinstance(error.detail, str) else "Request failed."
    return JSONResponse(
        status_code=error.status_code,
        content={"error": {"code": code, "message": message}},
    )


@app.get("/")
async def api_info() -> dict[str, str]:
    return {"name": "Relaydesk API", "version": __version__}
