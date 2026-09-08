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


class PublicAuthorOut(CamelModel):
    """Who wrote an article, as a reader sees it. Name and monogram only --
    an email address here would publish a staff address to the world."""

    name: str
    monogram: str


class ArticleOut(ArticleSummary):
    doc: dict
    published_at: datetime | None
    #: Who wrote it, for the console preview's byline -- the same one the
    #: help site prints. None where their account has been deleted.
    author: PublicAuthorOut | None = None


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
    """An entry in a collection listing or search results -- no body, no doc."""

    id: str
    title: str
    slug: str
    excerpt: str
    #: Slash-joined, no leading slash: "for-spenders/expenses/add-a-receipt".
    #: The href, carried with the article because a nested KB makes it
    #: impossible to derive from the slug.
    path: str


class PublicArticleOut(PublicArticleSummary):
    doc: dict
    #: None where the author's account has been deleted: `author_user_id`
    #: is SET NULL, and the article outlives them.
    author: PublicAuthorOut | None = None
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


class PublicSectionOut(CamelModel):
    """One card on a collection page: a section, and the rows it lists.

    The rows are of two kinds -- articles, and sub-collections with their
    own counts -- and a card mixes them freely, which is what the three
    container levels look like once drawn.
    """

    collection: PublicCollectionOut
    collections: list[PublicCollectionOut]
    articles: list[PublicArticleSummary]


class PublicCategoryNodeOut(CamelModel):
    kind: Literal["category"] = "category"
    category: PublicCollectionOut
    #: Root first, excluding the category itself.
    ancestors: list[PublicCrumbOut]
    sections: list[PublicSectionOut]
    #: Articles sitting directly here rather than in a section.
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
