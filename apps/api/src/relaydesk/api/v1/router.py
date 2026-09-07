"""The public API.

Mounted at ``/v1``, beside ``/api`` rather than under it (spec D7). ``/api``
is the console's private surface and is free to change with the UI; this one
is a promise to third parties. Keeping the two prefixes apart makes which is
which legible in the route table, and makes the published sample --
``https://api.relaydesk.dev/v1/conversations`` -- true with no proxy
rewriting.
"""

from fastapi import APIRouter

from relaydesk.api.v1.conversations import router as conversations_router

v1_router = APIRouter()
v1_router.include_router(
    conversations_router, prefix="/conversations", tags=["v1: conversations"]
)
