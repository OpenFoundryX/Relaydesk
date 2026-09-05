import hashlib
import uuid
from pathlib import Path

import pytest

from relaydesk.errors import NotFound
from relaydesk.services import blobs


def test_content_is_addressed_by_hash(tmp_path: Path) -> None:
    workspace_id = uuid.uuid4()

    digest, key = blobs.write(tmp_path, workspace_id, b"hello")

    assert digest == hashlib.sha256(b"hello").hexdigest()
    assert key == f"{workspace_id}/{digest}"
    assert (tmp_path / str(workspace_id) / digest).read_bytes() == b"hello"


def test_identical_bytes_are_written_once(tmp_path: Path) -> None:
    workspace_id = uuid.uuid4()

    first, _ = blobs.write(tmp_path, workspace_id, b"same")
    second, _ = blobs.write(tmp_path, workspace_id, b"same")

    assert first == second
    assert [p.name for p in (tmp_path / str(workspace_id)).iterdir()] == [first]


def test_two_workspaces_do_not_share_a_path(tmp_path: Path) -> None:
    one, two = uuid.uuid4(), uuid.uuid4()

    blobs.write(tmp_path, one, b"same")
    blobs.write(tmp_path, two, b"same")

    assert blobs.read(tmp_path, one, hashlib.sha256(b"same").hexdigest()) == b"same"
    assert (tmp_path / str(one)).exists()
    assert (tmp_path / str(two)).exists()


def test_a_hostile_hash_cannot_escape_the_workspace_directory(tmp_path: Path) -> None:
    """The containment check is the only thing between one tenant's files and
    another's. Without it this resolves to a real file outside the root."""
    workspace_id = uuid.uuid4()
    (tmp_path / str(workspace_id)).mkdir(parents=True)
    (tmp_path / "secret").write_bytes(b"not yours")

    with pytest.raises(NotFound):
        blobs.read(tmp_path, workspace_id, "../secret")


def test_a_missing_blob_raises_not_found(tmp_path: Path) -> None:
    with pytest.raises(NotFound):
        blobs.read(tmp_path, uuid.uuid4(), "0" * 64)
