import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from relaydesk import __version__
from relaydesk.api.router import api_router
from relaydesk.api.v1.router import v1_router
from relaydesk.config import get_settings
from relaydesk.errors import AppError
from relaydesk.middleware import MaxBodySizeMiddleware

logger = logging.getLogger("relaydesk")
settings = get_settings()

app = FastAPI(title="Relaydesk API", version=__version__)
# `add_middleware` inserts at the front of the stack, so this one is added
# *before* CORS in order to end up *inside* it: nothing between here and the
# router reads a request body, so this still answers before any parsing
# happens, and sitting inside CORSMiddleware means the 413 it returns comes
# back with the CORS headers a browser needs to read it.
app.add_middleware(MaxBodySizeMiddleware, max_bytes=settings.max_request_bytes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")
app.include_router(v1_router, prefix="/v1")


@app.exception_handler(AppError)
async def handle_app_error(_: Request, error: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={"error": {"code": error.code, "message": error.message}},
        headers=error.headers,
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


# Anything that isn't an AppError, a validation error, or an HTTPException
# would otherwise escape as Starlette's plain-text "Internal Server Error",
# which the web client's `body.error.code` parsing cannot read. The envelope
# is deliberately generic — exception text and tracebacks go to the log, not
# to the response.
@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
    logger.error(
        "Unhandled error serving %s %s",
        request.method,
        request.url.path,
        exc_info=error,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {"code": "error", "message": "Something went wrong on our end."}
        },
    )


@app.get("/")
async def api_info() -> dict[str, str]:
    return {"name": "Relaydesk API", "version": __version__}
