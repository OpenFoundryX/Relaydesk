from pydantic import Field

from relaydesk.schemas.base import CamelModel


class CategoryOut(CamelModel):
    id: str
    name: str
    slug: str
    scope: str
    position: int
    article_count: int


class CategoryCreateRequest(CamelModel):
    name: str = Field(min_length=1, max_length=120)
    scope: str


class CategoryPatch(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    position: int | None = None
