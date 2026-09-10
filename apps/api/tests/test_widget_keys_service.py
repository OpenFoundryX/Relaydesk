from datetime import UTC, datetime, timedelta

import pytest

from relaydesk.errors import Invalid, NotFound
from relaydesk.services import widget_keys
from tests.factories import make_workspace


async def test_create_mints_a_prefixed_key(db_session):
    workspace = await make_workspace(db_session)
    created = await widget_keys.create(db_session, workspace.id, "Marketing site")

    assert created.key.startswith("rdw_")
    assert len(created.key) == 36
    assert created.allowed_origins == []


async def test_create_normalises_origins(db_session):
    workspace = await make_workspace(db_session)
    created = await widget_keys.create(
        db_session,
        workspace.id,
        "Site",
        allowed_origins=["HTTPS://ACME.COM/", "https://acme.com:443"],
    )

    # Both inputs are the same origin; it is stored once, normalised.
    assert created.allowed_origins == ["https://acme.com"]


async def test_create_refuses_an_unparseable_origin(db_session):
    workspace = await make_workspace(db_session)
    with pytest.raises(Invalid):
        await widget_keys.create(
            db_session, workspace.id, "Site", allowed_origins=["*.acme.com"]
        )


async def test_resolve_finds_an_active_key(db_session):
    workspace = await make_workspace(db_session)
    created = await widget_keys.create(db_session, workspace.id, "Site")

    found = await widget_keys.resolve(db_session, created.key)
    assert found.id == created.id


async def test_resolve_refuses_unknown_and_inactive_alike(db_session):
    """Same exception either way -- a caller must not learn which keys exist."""
    workspace = await make_workspace(db_session)
    created = await widget_keys.create(db_session, workspace.id, "Site")
    await widget_keys.update(db_session, workspace.id, created.id, active=False)

    with pytest.raises(NotFound):
        await widget_keys.resolve(db_session, created.key)
    with pytest.raises(NotFound):
        await widget_keys.resolve(db_session, "rdw_" + "0" * 32)


async def test_get_is_scoped_to_its_workspace(db_session):
    one = await make_workspace(db_session, slug="one")
    two = await make_workspace(db_session, slug="two")
    created = await widget_keys.create(db_session, one.id, "Site")

    with pytest.raises(NotFound):
        await widget_keys.get(db_session, two.id, created.id)


async def test_touch_writes_at_most_once_a_minute(db_session):
    workspace = await make_workspace(db_session)
    created = await widget_keys.create(db_session, workspace.id, "Site")

    await widget_keys.touch(db_session, created)
    first = created.last_seen_at
    assert first is not None

    await widget_keys.touch(db_session, created)
    assert created.last_seen_at == first

    created.last_seen_at = datetime.now(UTC) - timedelta(minutes=2)
    await widget_keys.touch(db_session, created)
    assert created.last_seen_at != first


# Branding settings (spec D10, un-deferred). Every field is optional and
# absent means today's unbranded behaviour, unchanged -- these tests cover
# what "clean" means for each field, and the two rejections the design brief
# calls out by name: a bad colour and a bad position.
class TestSettingsValidation:
    async def test_create_accepts_a_full_valid_settings_blob(self, db_session):
        workspace = await make_workspace(db_session)
        created = await widget_keys.create(
            db_session,
            workspace.id,
            "Site",
            settings={
                "name": "Acme Support",
                "greeting": "Hi! Need a hand?",
                "accentColour": "#4F46E5",
                "position": "left",
            },
        )

        assert created.settings == {
            "name": "Acme Support",
            "greeting": "Hi! Need a hand?",
            "accentColour": "#4F46E5",
            "position": "left",
        }

    async def test_create_defaults_settings_to_an_empty_object(self, db_session):
        workspace = await make_workspace(db_session)
        created = await widget_keys.create(db_session, workspace.id, "Site")

        assert created.settings == {}

    async def test_create_accepts_a_3_hex_colour(self, db_session):
        workspace = await make_workspace(db_session)
        created = await widget_keys.create(
            db_session, workspace.id, "Site", settings={"accentColour": "#fff"}
        )

        assert created.settings["accentColour"] == "#fff"

    async def test_create_refuses_a_non_hex_colour(self, db_session):
        """The colour lands directly in an inline style on a stranger's
        page -- an unvalidated value there is an injection surface."""
        workspace = await make_workspace(db_session)
        with pytest.raises(Invalid):
            await widget_keys.create(
                db_session,
                workspace.id,
                "Site",
                settings={"accentColour": "red; background:url(javascript:alert(1))"},
            )

    async def test_create_refuses_an_unknown_position(self, db_session):
        workspace = await make_workspace(db_session)
        with pytest.raises(Invalid):
            await widget_keys.create(
                db_session, workspace.id, "Site", settings={"position": "top"}
            )

    async def test_create_refuses_an_oversized_name(self, db_session):
        workspace = await make_workspace(db_session)
        with pytest.raises(Invalid):
            await widget_keys.create(
                db_session, workspace.id, "Site", settings={"name": "x" * 200}
            )

    async def test_create_refuses_an_oversized_greeting(self, db_session):
        workspace = await make_workspace(db_session)
        with pytest.raises(Invalid):
            await widget_keys.create(
                db_session, workspace.id, "Site", settings={"greeting": "x" * 500}
            )

    async def test_create_refuses_an_unknown_setting_key(self, db_session):
        workspace = await make_workspace(db_session)
        with pytest.raises(Invalid):
            await widget_keys.create(
                db_session, workspace.id, "Site", settings={"unknownField": "x"}
            )

    async def test_create_refuses_a_non_string_name(self, db_session):
        workspace = await make_workspace(db_session)
        with pytest.raises(Invalid):
            await widget_keys.create(
                db_session, workspace.id, "Site", settings={"name": 123}
            )

    async def test_create_refuses_icon_url_as_an_unknown_setting(self, db_session):
        """Not yet accepted: an icon has nowhere to be served from (see this
        slice's report), and a settable field nothing renders is the exact
        defect D10 already shipped once. Pinned so a future change that adds
        `iconUrl` back has to do so deliberately, alongside where it renders,
        rather than by accident."""
        workspace = await make_workspace(db_session)
        with pytest.raises(Invalid):
            await widget_keys.create(
                db_session,
                workspace.id,
                "Site",
                settings={"iconUrl": "https://acme.com/icon.png"},
            )

    async def test_create_strips_trailing_whitespace_from_accent_colour(
        self, db_session
    ):
        """`_HEX_COLOUR_RE` used to anchor with `^...$`, and Python's `$`
        matches immediately before a trailing newline, so "#4F46E5\\n" would
        pass and be stored unstripped -- inconsistent with `name`/`greeting`,
        which are always stripped. `fullmatch` plus an explicit `.strip()`
        closes that."""
        workspace = await make_workspace(db_session)
        created = await widget_keys.create(
            db_session, workspace.id, "Site", settings={"accentColour": "#4F46E5\n"}
        )

        assert created.settings["accentColour"] == "#4F46E5"

    async def test_update_validates_settings_the_same_way(self, db_session):
        workspace = await make_workspace(db_session)
        created = await widget_keys.create(db_session, workspace.id, "Site")

        with pytest.raises(Invalid):
            await widget_keys.update(
                db_session,
                workspace.id,
                created.id,
                settings={"position": "up"},
            )

    async def test_update_replaces_settings_wholesale(self, db_session):
        workspace = await make_workspace(db_session)
        created = await widget_keys.create(
            db_session,
            workspace.id,
            "Site",
            settings={"name": "Old", "position": "left"},
        )

        updated = await widget_keys.update(
            db_session,
            workspace.id,
            created.id,
            settings={"greeting": "New greeting"},
        )

        # A PATCH's settings replace the blob, the same way allowed_origins
        # does -- there is no per-field merge.
        assert updated.settings == {"greeting": "New greeting"}
