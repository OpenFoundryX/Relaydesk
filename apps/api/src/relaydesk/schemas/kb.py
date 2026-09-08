import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, field_validator

from relaydesk.schemas.base import CamelModel


def _reject_blank(value: str | None) -> str | None:
    """`min_length=1` only counts characters, so "   " passes it and the
    service's own `.strip()` would then store an empty title -- an empty
    `<h1>` on the public site, with the slug falling back to "untitled".
    Rejecting here keeps that decision at the schema boundary rather than
    letting it depend on what the service happens to do with the value.
    """
    if value is not None and not value.strip():
        raise ValueError("Title cannot be blank.")
    return value


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

    _validate_title = field_validator("title")(_reject_blank)


class ArticlePatch(CamelModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    excerpt: str | None = Field(default=None, max_length=400)
    doc: dict | None = None
    category_id: uuid.UUID | None = None

    _validate_title = field_validator("title")(_reject_blank)


class StatusRequest(CamelModel):
    status: str


class ImageOut(CamelModel):
    id: str
    url: str


class PublicWorkspaceOut(CamelModel):
    """The anonymous, subdomain-resolved view of a workspace.

    Deliberately minimal: name and monogram are all the portal chrome
    needs, and nothing else here is safe to hand to an unauthenticated
    caller (plan, seat counts, ticket volume, ...).
    """

    name: str
    monogram: str


class PublicArticleSummary(CamelModel):
    """An entry in the index or search results -- no body, no doc."""

    id: str
    title: str
    slug: str
    excerpt: str


class PublicArticleOut(PublicArticleSummary):
    doc: dict
    published_at: datetime | None
    #: When the article last changed. The help site prints it under the body
    #: as "Last updated", which is the one thing a reader needs to judge
    #: whether an answer is still current. Safe to publish: it says when a
    #: *published* article was edited, not who edited it, and every article
    #: this schema is ever built for is already public.
    updated_at: datetime


class PublicCollectionOut(CamelModel):
    """A collection as it appears on a card: blurb, icon, and a count.

    `article_count` is the whole subtree, not the direct children -- a
    collection whose articles all live in its sections would otherwise
    advertise zero.
    """

    id: str
    name: str
    slug: str
    description: str
    icon: str
    article_count: int


class PublicCrumbOut(CamelModel):
    """One step of a breadcrumb. Name to print, slug to build the href."""

    name: str
    slug: str


class PublicCategoryNodeOut(CamelModel):
    kind: Literal["category"] = "category"
    category: PublicCollectionOut
    #: Root first, excluding the category itself.
    ancestors: list[PublicCrumbOut]
    collections: list[PublicCollectionOut]
    #: Articles sitting directly here rather than in a sub-collection.
    articles: list[PublicArticleSummary]


class PublicArticleNodeOut(CamelModel):
    kind: Literal["article"] = "article"
    article: PublicArticleOut
    ancestors: list[PublicCrumbOut]


#: What a help-site path resolves to. The caller -- one catch-all route --
#: cannot know which of the two it is asking for, so `kind` tells it.
PublicNodeOut = Annotated[
    PublicCategoryNodeOut | PublicArticleNodeOut, Field(discriminator="kind")
]


class TicketSubmittedOut(CamelModel):
    """Deliberately says nothing but "received". No id, no number: the
    submitter is anonymous and must not be handed a handle to the inbox."""

    received: bool
