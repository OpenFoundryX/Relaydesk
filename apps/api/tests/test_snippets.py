import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from relaydesk.errors import Conflict, Invalid, NotFound
from relaydesk.services import snippets
from tests.factories import make_workspace


async def test_a_snippet_is_stored_with_its_title_and_content(
    db_session: AsyncSession,
) -> None:
    workspace = await make_workspace(db_session)

    snippet = await snippets.create(
        db_session, workspace.id, "Follow up", "Just checking in — any luck?"
    )

    assert snippet.title == "Follow up"
    assert snippet.content == "Just checking in — any luck?"


async def test_surrounding_whitespace_is_trimmed_off_the_title(
    db_session: AsyncSession,
) -> None:
    workspace = await make_workspace(db_session)

    snippet = await snippets.create(db_session, workspace.id, "  Greeting  ", "Hi!")

    assert snippet.title == "Greeting"


@pytest.mark.parametrize("title", ["", "   "])
async def test_a_blank_title_is_rejected(db_session: AsyncSession, title: str) -> None:
    """`min_length=1` at the schema counts characters, so "   " reaches the
    service. A snippet with no title is unreachable: the `/` menu in the
    composer has nothing to match on and nothing to show."""
    workspace = await make_workspace(db_session)

    with pytest.raises(Invalid):
        await snippets.create(db_session, workspace.id, title, "Hi!")


@pytest.mark.parametrize("content", ["", "   "])
async def test_blank_content_is_rejected(
    db_session: AsyncSession, content: str
) -> None:
    workspace = await make_workspace(db_session)

    with pytest.raises(Invalid):
        await snippets.create(db_session, workspace.id, "Greeting", content)


async def test_a_duplicate_title_is_a_conflict(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)
    await snippets.create(db_session, workspace.id, "Greeting", "Hi!")

    with pytest.raises(Conflict):
        await snippets.create(db_session, workspace.id, "Greeting", "Hello!")


async def test_a_title_differing_only_in_case_is_a_conflict(
    db_session: AsyncSession,
) -> None:
    """The title is what an agent types after `/`. Two snippets that read
    the same in that menu cannot be told apart, so the column is CITEXT and
    the collision is refused rather than stored."""
    workspace = await make_workspace(db_session)
    await snippets.create(db_session, workspace.id, "Greeting", "Hi!")

    with pytest.raises(Conflict):
        await snippets.create(db_session, workspace.id, "greeting", "Hello!")


async def test_the_same_title_in_another_workspace_is_allowed(
    db_session: AsyncSession,
) -> None:
    one = await make_workspace(db_session, slug="chronon")
    two = await make_workspace(db_session, slug="northwind")
    await snippets.create(db_session, one.id, "Greeting", "Hi!")

    await snippets.create(db_session, two.id, "Greeting", "Hello!")


async def test_snippets_list_in_title_order(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)
    await snippets.create(db_session, workspace.id, "Thank you", "Thanks!")
    await snippets.create(db_session, workspace.id, "Greeting", "Hi!")

    rows = await snippets.list_for(db_session, workspace.id)

    assert [row.title for row in rows] == ["Greeting", "Thank you"]


async def test_another_workspaces_snippets_are_not_listed(
    db_session: AsyncSession,
) -> None:
    one = await make_workspace(db_session, slug="chronon")
    two = await make_workspace(db_session, slug="northwind")
    await snippets.create(db_session, two.id, "Greeting", "Hi!")

    assert await snippets.list_for(db_session, one.id) == []


async def test_updating_a_snippet_changes_its_content(
    db_session: AsyncSession,
) -> None:
    workspace = await make_workspace(db_session)
    snippet = await snippets.create(db_session, workspace.id, "Greeting", "Hi!")

    updated = await snippets.update(
        db_session, workspace.id, snippet.id, content="Hello there!"
    )

    assert updated.content == "Hello there!"
    assert updated.title == "Greeting"


async def test_renaming_onto_an_existing_title_is_a_conflict(
    db_session: AsyncSession,
) -> None:
    workspace = await make_workspace(db_session)
    await snippets.create(db_session, workspace.id, "Greeting", "Hi!")
    other = await snippets.create(db_session, workspace.id, "Thank you", "Thanks!")

    with pytest.raises(Conflict):
        await snippets.update(db_session, workspace.id, other.id, title="Greeting")


async def test_a_snippet_can_be_saved_under_its_own_title(
    db_session: AsyncSession,
) -> None:
    """The edit dialog submits every field, title included, so an edit that
    only touches the content still sends the unchanged title back. That must
    not read as a collision with the row being edited."""
    workspace = await make_workspace(db_session)
    snippet = await snippets.create(db_session, workspace.id, "Greeting", "Hi!")

    updated = await snippets.update(
        db_session, workspace.id, snippet.id, title="Greeting", content="Hello!"
    )

    assert updated.content == "Hello!"


async def test_updating_a_snippet_in_another_workspace_is_not_found(
    db_session: AsyncSession,
) -> None:
    one = await make_workspace(db_session, slug="chronon")
    two = await make_workspace(db_session, slug="northwind")
    snippet = await snippets.create(db_session, two.id, "Greeting", "Hi!")

    with pytest.raises(NotFound):
        await snippets.update(db_session, one.id, snippet.id, content="Hello!")


async def test_deleting_a_snippet_removes_it(db_session: AsyncSession) -> None:
    workspace = await make_workspace(db_session)
    snippet = await snippets.create(db_session, workspace.id, "Greeting", "Hi!")

    await snippets.delete(db_session, workspace.id, snippet.id)

    assert await snippets.list_for(db_session, workspace.id) == []


async def test_deleting_another_workspaces_snippet_is_not_found(
    db_session: AsyncSession,
) -> None:
    one = await make_workspace(db_session, slug="chronon")
    two = await make_workspace(db_session, slug="northwind")
    snippet = await snippets.create(db_session, two.id, "Greeting", "Hi!")

    with pytest.raises(NotFound):
        await snippets.delete(db_session, one.id, snippet.id)
