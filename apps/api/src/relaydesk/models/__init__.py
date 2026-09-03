"""SQLAlchemy models.

Every model must be imported here so ``Base.metadata`` is complete when
Alembic autogenerates a migration.
"""

from relaydesk.db.base import Base
from relaydesk.models.workspace import Workspace

__all__ = ["Base", "Workspace"]
