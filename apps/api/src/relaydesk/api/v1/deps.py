import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Request, Response

from relaydesk.api.deps import DbSession, bearer_token
from relaydesk.config import get_settings
from relaydesk.errors import Forbidden, TooManyRequests, Unauthorized
from relaydesk.models import ApiKey, ApiKeyScope, Workspace
from relaydesk.services import api_keys, api_usage
from relaydesk.services.actors import Actor


@dataclass(slots=True)
class ApiPrincipal:
    """Resolved tenant context for a key-authenticated call.

    The public-surface counterpart to ``WorkspaceScope``, and deliberately
    not the same object. ``WorkspaceScope.user`` is non-null at every one of
    its call sites, several of which hand it straight to a service; making it
    optional to accommodate a principal no console route uses would turn a
    compile-time guarantee into a runtime audit of every console route (spec
    D2). The two meet at the service layer instead, through ``Actor``.
    """

    key: ApiKey
    workspace: Workspace

    @property
    def workspace_id(self) -> uuid.UUID:
        return self.workspace.id

    @property
    def actor(self) -> Actor:
        return Actor.for_key(self.key)

    def require(self, *scopes: ApiKeyScope) -> None:
        for scope in scopes:
            if scope.value not in self.key.scopes:
                # Naming the missing scope is safe: the caller holds this key
                # and can already read its scopes in the console. Withholding
                # it would only make a correct integration harder to write.
                raise Forbidden(f"This key needs the {scope.value} scope.")


async def api_principal(
    session: DbSession,
    request: Request,
    response: Response,
    token: Annotated[str, Depends(bearer_token)],
) -> ApiPrincipal:
    """Authenticate the key and charge the call against its limit.

    The charge happens here, before the route body, so a refused caller
    never reaches the work -- and it happens on every call, including ones
    that go on to 404, because a probe is still a call.
    """
    key = await api_keys.resolve(session, token)
    workspace = await session.get(Workspace, key.workspace_id)
    if workspace is None:
        raise Unauthorized(api_keys.BAD_KEY)

    limit = get_settings().api_key_rate_limit_per_minute
    allowed, remaining = await api_usage.charge(session, key.id, limit=limit)
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    # FastAPI only merges a dependency's ``Response`` headers into the real
    # response *after* the route handler returns successfully -- an
    # exception raised anywhere downstream (a missing scope, a
    # cross-workspace 404, a bad query param) unwinds straight to an
    # exception handler in ``main.py`` that builds a fresh ``JSONResponse``
    # and never sees this ``response`` object. Stashing the pair on
    # ``request.state`` gives those handlers something to read regardless of
    # which way the request ends, so a charged-but-refused call still tells
    # the caller its budget.
    request.state.rate_limit = (limit, remaining)
    if not allowed:
        # The headers set above belong to the *success* response object; an
        # exception bypasses it, so the refusal carries its own copy.
        raise TooManyRequests(
            "Rate limit exceeded for this API key.",
            headers={
                "Retry-After": "60",
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
            },
        )

    return ApiPrincipal(key=key, workspace=workspace)


Principal = Annotated[ApiPrincipal, Depends(api_principal)]


def requires(
    *scopes: ApiKeyScope,
) -> Callable[[ApiPrincipal], Coroutine[Any, Any, ApiPrincipal]]:
    """A dependency that authenticates and then demands specific scopes.

    Every v1 route declares its own, so the scope a route needs is written
    next to the route rather than in a table somewhere else -- and it shows
    up in the generated OpenAPI document as part of the signature.
    """

    async def dependency(principal: Principal) -> ApiPrincipal:
        principal.require(*scopes)
        return principal

    return dependency
