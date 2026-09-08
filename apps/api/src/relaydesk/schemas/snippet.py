from pydantic import Field, field_validator

from relaydesk.schemas.base import CamelModel

#: A snippet is a reply fragment, not an article -- the knowledge base is
#: where a long answer belongs. The bound is here so an oversized body is a
#: 422 at the edge rather than an unbounded row in `snippets.content`.
CONTENT_MAX = 4000


def _reject_blank(value: str | None) -> str | None:
    """`min_length=1` only counts characters, so "   " passes it and the
    service would then be asked to store a snippet with a blank title -- an
    entry in the composer's `/` menu with nothing to read and nothing to
    match on."""
    if value is not None and not value.strip():
        raise ValueError("This field cannot be blank.")
    return value


class SnippetOut(CamelModel):
    id: str
    title: str
    content: str


class SnippetCreateRequest(CamelModel):
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=CONTENT_MAX)

    _validate_title = field_validator("title")(_reject_blank)
    _validate_content = field_validator("content")(_reject_blank)


class SnippetPatch(CamelModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    content: str | None = Field(default=None, min_length=1, max_length=CONTENT_MAX)

    _validate_title = field_validator("title")(_reject_blank)
    _validate_content = field_validator("content")(_reject_blank)
