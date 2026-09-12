from fastapi import APIRouter

from relaydesk.api.deps import DbSession, Scope
from relaydesk.models.ai_config import AiConfig
from relaydesk.schemas.ai_config import AiConfigIn, AiConfigOut
from relaydesk.services import ai_configs

router = APIRouter()


def _out(config: AiConfig) -> AiConfigOut:
    return AiConfigOut(
        provider=config.provider,
        model=config.model,
        base_url=config.base_url,
        daily_token_budget=config.daily_token_budget,
        enabled=config.enabled,
        key_suffix=config.api_key[-4:] if config.api_key else None,
    )


@router.get("", response_model=AiConfigOut)
async def read_route(scope: Scope, session: DbSession) -> AiConfigOut:
    scope.require_admin()
    config = await ai_configs.get_or_create(session, scope.workspace.id)
    await session.commit()
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
