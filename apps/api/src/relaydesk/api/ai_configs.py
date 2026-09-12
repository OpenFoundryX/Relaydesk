from fastapi import APIRouter

from relaydesk.api.deps import DbSession, Scope
from relaydesk.models.ai_config import (
    DEFAULT_DAILY_TOKEN_BUDGET,
    DEFAULT_MODEL,
    AiConfig,
)
from relaydesk.schemas.ai_config import AiConfigIn, AiConfigOut
from relaydesk.services import ai_configs

router = APIRouter()


# A key short enough that its last four characters ARE the key must not be
# echoed back. Real provider keys are around a hundred characters, so this
# guards a mistake rather than an attack -- but "never returned" is the one
# promise this screen exists to keep, and a promise with an exception is a
# different promise.
_MIN_MASKABLE_KEY = 12


def _suffix(api_key: str | None) -> str | None:
    """The last four characters, or nothing if that would reveal too much."""
    if not api_key or len(api_key) < _MIN_MASKABLE_KEY:
        return None
    return api_key[-4:]


def _out(config: AiConfig) -> AiConfigOut:
    return AiConfigOut(
        provider=config.provider,
        model=config.model,
        base_url=config.base_url,
        daily_token_budget=config.daily_token_budget,
        enabled=config.enabled,
        key_suffix=_suffix(config.api_key),
    )


@router.get("", response_model=AiConfigOut)
async def read_route(scope: Scope, session: DbSession) -> AiConfigOut:
    """This workspace's model configuration, or the defaults it would get.

    Deliberately does not create the row. Reading a settings screen should
    not write to the database -- a monitor or a browser prefetch would
    otherwise leave rows behind -- and nothing downstream needs one to
    exist: both `ai_answers` and `ai_provider` treat a missing config as an
    unconfigured workspace. `PUT` is the only writer.
    """
    scope.require_admin()
    config = await session.get(AiConfig, scope.workspace.id)
    if config is None:
        # Not `_out(AiConfig(...))`: SQLAlchemy column defaults are applied
        # at INSERT, so an unsaved instance has None for every one of them
        # and the screen would render blank fields instead of the defaults
        # a workspace would actually get.
        return AiConfigOut(
            provider="anthropic",
            model=DEFAULT_MODEL,
            base_url=None,
            daily_token_budget=DEFAULT_DAILY_TOKEN_BUDGET,
            enabled=False,
            key_suffix=None,
        )
    return _out(config)


@router.put("", response_model=AiConfigOut)
async def write_route(
    body: AiConfigIn, scope: Scope, session: DbSession
) -> AiConfigOut:
    scope.require_admin()
    config = await ai_configs.update(
        session,
        scope.workspace.id,
        provider=body.provider,
        model=body.model,
        api_key=body.api_key,
        base_url=body.base_url,
        daily_token_budget=body.daily_token_budget,
        enabled=body.enabled,
    )
    await session.commit()
    return _out(config)
