import pytest

from relaydesk.api.deps import WorkspaceScope
from relaydesk.errors import Forbidden
from relaydesk.models import Membership, MembershipStatus, Role, User, Workspace


def make_scope(role: Role) -> WorkspaceScope:
    user = User(email="agent@relaydesk.dev", name="Agent", monogram="AG")
    workspace = Workspace(name="Chronon", slug="chronon", monogram="CH")
    membership = Membership(role=role, status=MembershipStatus.active)
    return WorkspaceScope(user=user, membership=membership, workspace=workspace)


def test_require_admin_allows_an_admin() -> None:
    scope = make_scope(Role.admin)

    scope.require_admin()  # does not raise


def test_require_admin_rejects_an_agent() -> None:
    scope = make_scope(Role.agent)

    with pytest.raises(Forbidden):
        scope.require_admin()
