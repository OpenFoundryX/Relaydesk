"""ASGI middleware that runs before anything reads a request body."""

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from relaydesk.errors import PayloadTooLarge


class MaxBodySizeMiddleware:
    """Refuse an oversized body from its Content-Length, without reading it.

    This has to be ASGI middleware rather than anything FastAPI-shaped.
    `POST /api/public/{slug}/tickets` declares `Form`/`File` parameters, so
    Starlette parses and spools the entire multipart body while resolving
    that route's dependencies -- before the route function runs, and so
    before the IP rate limiter inside it has had any chance to refuse the
    caller. An anonymous caller who is already over its cap would otherwise
    still get the process to read an unbounded body on every attempt, and
    there is no ingress limit in front of this service (docker-compose
    publishes it on 8000 directly).

    Answering from the declared Content-Length alone means nothing is read.
    A request that declares no length at all is left to the app: over
    HTTP/1.1 that means either no body or a chunked one -- see the note in
    the final review report about the chunked case.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = Headers(scope=scope).get("content-length")
        if declared is not None:
            try:
                length = int(declared)
            except ValueError:
                # A malformed length is the server's problem to reject, not
                # ours to guess at; the protocol layer already refuses it.
                length = 0
            if length > self.max_bytes:
                error = PayloadTooLarge("That request is too large.")
                response = JSONResponse(
                    status_code=error.status_code,
                    content={
                        "error": {"code": error.code, "message": error.message}
                    },
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)
