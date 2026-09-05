import uuid
from datetime import datetime

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


class ArticleSummary(CamelModel):
    id: str
    title: str
    slug: str
    excerpt: str
    status: str
    category_id: str
    updated_at: datetime


class ArticleOut(ArticleSummary):
    doc: dict
    published_at: datetime | None


class ArticleCreateRequest(CamelModel):
    category_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)


class ArticlePatch(CamelModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    excerpt: str | None = Field(default=None, max_length=400)
    doc: dict | None = None
    category_id: uuid.UUID | None = None


class StatusRequest(CamelModel):
    status: str


class ImageOut(CamelModel):
    id: str
    url: str
