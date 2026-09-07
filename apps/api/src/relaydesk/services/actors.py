import uuid
from dataclasses import dataclass

from relaydesk.models.api_key import ApiKey
from relaydesk.models.user import User


@dataclass(frozen=True, slots=True)
class Actor:
    """Whoever caused a change, whether or not they are a person.

    The persistence layer was already built for this shape before there was
    a name for it: ``activity_events`` and ``messages`` both carry a
    nullable actor foreign key beside a name *snapshot*, because inbound
    mail has always produced activity that no signed-in user caused. This
    type is that pattern made explicit, with a second nullable key for the
    principal added in slice 6.

    The name is a snapshot on purpose. It is what history displays, and it
    must keep displaying after the key is revoked or the user is removed --
    which is exactly when both foreign keys go ``NULL``.
    """

    name: str
    user_id: uuid.UUID | None = None
    api_key_id: uuid.UUID | None = None

    @classmethod
    def for_user(cls, user: User) -> "Actor":
        return cls(name=user.name, user_id=user.id)

    @classmethod
    def for_key(cls, key: ApiKey) -> "Actor":
        return cls(name=key.name, api_key_id=key.id)
