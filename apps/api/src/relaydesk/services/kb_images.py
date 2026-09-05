"""Images embedded in knowledge base articles.

Unlike message attachments, these are rendered inline -- that is what an
image in an article is for -- so the upload allowlist is narrower than the
attachment one: only types that are safe to render, which excludes SVG
because it executes script.
"""

import uuid
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.config import get_settings
from relaydesk.errors import Invalid, NotFound
from relaydesk.models.kb import KbArticle, KbImage
from relaydesk.services import blobs
from relaydesk.services.attachments import INLINE_SAFE_TYPES


def storage_root() -> Path:
    """Public because kb_public reads images through the same root."""
    return Path(get_settings().attachment_dir)


async def store(
    session: AsyncSession,
    article: KbArticle,
    filename: str,
    content_type: str,
    content: bytes,
) -> KbImage:
    if content_type.lower() not in INLINE_SAFE_TYPES:
        raise Invalid(
            "Only PNG, JPEG, GIF, and WebP images can be added to an article."
        )

    cap = get_settings().kb_image_max_bytes
    if len(content) > cap:
        raise Invalid(f"That image is larger than the {cap // 1024 // 1024} MB limit.")

    digest, key = blobs.write(storage_root(), article.workspace_id, content)
    image = KbImage(
        workspace_id=article.workspace_id,
        article_id=article.id,
        filename=filename[:255],
        content_type=content_type.lower(),
        size_bytes=len(content),
        sha256=digest,
        storage_key=key,
    )
    session.add(image)
    await session.flush()
    return image


async def read(
    session: AsyncSession, workspace_id: uuid.UUID, image_id: uuid.UUID
) -> tuple[KbImage, bytes]:
    row = await session.scalar(
        sa.select(KbImage).where(
            KbImage.id == image_id, KbImage.workspace_id == workspace_id
        )
    )
    if row is None:
        raise NotFound("That image does not exist.")
    return row, blobs.read(storage_root(), workspace_id, row.sha256)
