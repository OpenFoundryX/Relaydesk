"""Content-addressed storage for bytes that arrived from outside.

Files live at ``<root>/<workspace id>/<sha256>``. The name a sender or
uploader chose never reaches a path: the hash is what makes traversal
structurally impossible rather than merely filtered.

Extracted from the attachment store so message attachments and knowledge-base
images share one implementation. The containment check on read exists because
a caller's stored key could be malformed by a bad migration or a second
writer, and a path that escapes its workspace directory would still have
matched on the ``workspace_id`` column.
"""

import hashlib
import uuid
from pathlib import Path

from relaydesk.errors import NotFound


def write(root: Path, workspace_id: uuid.UUID, content: bytes) -> tuple[str, str]:
    """Store ``content`` and return ``(sha256, storage_key)``."""
    directory = root / str(workspace_id)
    directory.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha256(content).hexdigest()
    path = directory / digest
    if not path.exists():
        # Write to a temporary name and rename, so a crash mid-write cannot
        # leave a truncated file at a hash that claims to be whole.
        temporary = directory / f".{digest}.{uuid.uuid4().hex}"
        temporary.write_bytes(content)
        temporary.rename(path)

    return digest, f"{workspace_id}/{digest}"


def read(root: Path, workspace_id: uuid.UUID, sha256: str) -> bytes:
    """Read a blob, refusing anything that resolves outside the workspace.

    The path is rebuilt from the validated ``workspace_id`` and the hash --
    never from a stored key -- and the descendant check is what holds when
    the hash itself is hostile.
    """
    base = (root / str(workspace_id)).resolve()
    path = (base / sha256).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise NotFound("That file does not exist.")
    return path.read_bytes()
