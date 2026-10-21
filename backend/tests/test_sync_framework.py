"""The sync framework on a fake database with the fake connector (guide section 5)."""

from datetime import UTC, datetime

import pytest

from sync import normalize_phone, run_sync
from sync.connectors import build
from sync.connectors.fake import FakeConnector
from tests._fakes import FakeDb


def test_normalize_phone_accepts_e164_and_regional_numbers_only_with_a_region() -> None:
    assert normalize_phone("+48 600 000 001") == "+48600000001"
    assert normalize_phone("600 000 002", "PL") == "+48600000002"
    assert normalize_phone("600 000 002") is None  # no prefix, no region: not guessed
    assert normalize_phone("12345", "PL") is None
    assert normalize_phone("not a number") is None


@pytest.mark.anyio
async def test_first_sync_inserts_contacts_and_consents_and_skips_invalid_numbers() -> None:
    db = FakeDb()
    stats = await run_sync(db, FakeConnector(), since=None)
    assert stats.as_dict() == {
        "extracted": 4,
        "inserted": 3,
        "updated": 0,
        "unchanged": 0,
        "consents": 3,
        "invalid": 1,
    }
    contacts = {c["external_ref"]: c for c in db.rows("contacts")}
    assert sorted(contacts) == ["fake:u1", "fake:u2", "fake:u4"]
    assert contacts["fake:u2"]["phone_e164"] == "+48600000002"  # regional number, region PL
    assert contacts["fake:u1"]["attributes"] == {"source": "fake"}
    consents = {c["contact_id"]: c["status"] for c in db.rows("consents")}
    assert consents[contacts["fake:u4"]["id"]] == "opted_out"
    assert db.rows("consents")[0]["captured_at"] == "2026-10-01T10:00:00+00:00"


@pytest.mark.anyio
async def test_second_sync_changes_nothing_and_a_changed_record_updates_in_place() -> None:
    db = FakeDb()
    connector = FakeConnector()
    await run_sync(db, connector, since=None)
    again = await run_sync(db, connector, since=None)
    assert (again.inserted, again.updated, again.unchanged, again.consents) == (0, 0, 3, 0)

    connector.records[0].update({"phone": "+48600000099", "consent": "opted_out"})  # u1 moved
    changed = await run_sync(db, connector, since=None)
    assert (changed.inserted, changed.updated, changed.unchanged, changed.consents) == (0, 1, 2, 1)
    u1 = next(c for c in db.rows("contacts") if c["external_ref"] == "fake:u1")
    assert u1["phone_e164"] == "+48600000099"
    statuses = [c["status"] for c in db.rows("consents") if c["contact_id"] == u1["id"]]
    assert statuses == ["opted_in", "opted_out"]  # append-only, latest wins
    assert len(db.rows("contacts")) == 3


@pytest.mark.anyio
async def test_since_limits_extraction_and_batches_add_up() -> None:
    db = FakeDb()
    since = datetime(2026, 10, 2, 12, tzinfo=UTC)
    stats = await run_sync(db, FakeConnector(), since=since, batch_size=1)
    assert (stats.extracted, stats.inserted, stats.invalid) == (2, 1, 1)  # u3 invalid, u4 stored


def test_registry_builds_known_connectors_only() -> None:
    connector = build("fake", {"default_region": "DE", "fail": True})
    assert isinstance(connector, FakeConnector)
    assert (connector.default_region, connector.fail) == ("DE", True)
    with pytest.raises(KeyError, match="unknown connector nope"):
        build("nope", {})
