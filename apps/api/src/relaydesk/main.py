from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from relaydesk import __version__
from relaydesk.api.router import api_router
from relaydesk.config import get_settings

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


@app.get("/")
async def api_info() -> dict[str, str]:
    return {"name": "Relaydesk API", "version": __version__}
