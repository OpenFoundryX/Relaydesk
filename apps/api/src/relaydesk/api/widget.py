"""Anonymous routes the embedded widget calls, addressed by widget key.

A second front door onto `relaydesk.api.public`, not new domain logic. The
KB reads below resolve the key to a workspace and then call public.py's own
route functions by slug, so the mapping from domain objects to schemas has
exactly one implementation. The difference between the two doors is only
how the workspace is named -- by key rather than by slug, so an embed
survives a workspace being renamed (spec D3).

Mounted at its own `/widget` prefix rather than under `/public`, so it adds
no fixed first path segment there and needs no entry in `RESERVED_SLUGS`.

Route order is load-bearing: FastAPI matches in declaration order, so every
fixed segment must be declared above the `{path:path}` catch-all or it is
swallowed as an article path.
"""

from fastapi import APIRouter

from relaydesk.api import public
from relaydesk.api.deps import DbSession
from relaydesk.schemas.kb import (
    PublicArticleSummary,
    PublicCollectionOut,
    PublicNodeOut,
    PublicSearchEntryOut,
)
from relaydesk.schemas.widget import WidgetBootstrapOut
from relaydesk.services import kb_public, widget_keys

router = APIRouter()


@router.get("/{key}", response_model=WidgetBootstrapOut)
async def bootstrap(key: str, session: DbSession) -> WidgetBootstrapOut:
    """Everything the frame needs for its first paint, in one call.

    ``article_count`` is here rather than behind a second request because
    the empty-knowledge-base rendering (spec D7) is a different screen, not
    a different state of the same one -- fetching it later would show a
    search field for one frame and then take it away.

    It is the length of ``searchable()`` rather than its own COUNT query so
    that "the knowledge base is empty" means exactly "search would find
    nothing", by construction rather than by two queries agreeing.
    """
    widget_key = await widget_keys.resolve(session, key)
    await widget_keys.touch(session, widget_key)
    await session.commit()
    workspace = widget_key.workspace
    entries = await kb_public.searchable(session, workspace.id)

    return WidgetBootstrapOut(
        workspace_name=workspace.name,
        monogram=workspace.monogram,
        settings=widget_key.settings,
        article_count=len(entries),
    )


@router.get("/{key}/kb", response_model=list[PublicCollectionOut])
async def kb_index(key: str, session: DbSession) -> list[PublicCollectionOut]:
    widget_key = await widget_keys.resolve(session, key)
    return await public.read_kb_index(slug=widget_key.workspace.slug, session=session)


@router.get("/{key}/kb/search/index", response_model=list[PublicSearchEntryOut])
async def kb_search_index(key: str, session: DbSession) -> list[PublicSearchEntryOut]:
    """The whole searchable set, fetched once and searched in the browser.

    This is what removes search from the rate-limit surface entirely (spec
    D8). It discloses nothing new -- every entry is a published,
    externally-scoped article already served in full on the public help site.
    """
    widget_key = await widget_keys.resolve(session, key)
    return await public.read_kb_search_index(
        slug=widget_key.workspace.slug, session=session
    )


@router.get("/{key}/kb/search", response_model=list[PublicArticleSummary])
async def kb_search(
    key: str, session: DbSession, q: str = ""
) -> list[PublicArticleSummary]:
    """Server-side search, for indexes too large to ship whole (spec D8)."""
    widget_key = await widget_keys.resolve(session, key)
    return await public.search_kb(slug=widget_key.workspace.slug, session=session, q=q)


# Declared last: `{path:path}` matches anything, including the fixed
# segments above, so moving it up silently 404s them as missing articles.
@router.get("/{key}/kb/{path:path}", response_model=PublicNodeOut)
async def kb_node(key: str, path: str, session: DbSession) -> PublicNodeOut:
    widget_key = await widget_keys.resolve(session, key)
    return await public.read_kb_path(
        slug=widget_key.workspace.slug, path=path, session=session
    )
