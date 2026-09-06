class AppError(Exception):
    """Base for domain errors. Services raise these; routers map them."""

    code = "error"
    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class Invalid(AppError):
    code = "invalid"
    status_code = 422


class Unauthorized(AppError):
    code = "unauthorized"
    status_code = 401


class Forbidden(AppError):
    code = "forbidden"
    status_code = 403


class NotFound(AppError):
    code = "not_found"
    status_code = 404


class Conflict(AppError):
    code = "conflict"
    status_code = 409


class Unavailable(AppError):
    code = "unavailable"
    status_code = 503


class TooManyRequests(AppError):
    code = "too_many_requests"
    status_code = 429


class PayloadTooLarge(AppError):
    """The request body is bigger than this deployment will read.

    Raised by nothing in the service layer: the only thing that can refuse a
    body *before* it has been read is the ASGI middleware in
    `relaydesk.middleware`, which builds this error's envelope itself
    because middleware runs outside FastAPI's exception handlers. It lives
    here so that envelope has exactly one definition.
    """

    code = "too_large"
    status_code = 413
