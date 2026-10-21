"""The postgres connector: query building and mapping without a database; a live read when
SYNC_POSTGRES_DSN points at a database with the demo table (local Supabase)."""

import os
from datetime import UTC, datetime

import pytest

from sync.connectors import build
from sync.connectors.postgres import PostgresConnector
from sync.framework import ConsentChange, run_sync
from tests._fakes import FakeDb

CONFIG = {
    "table": "legacy.contacts",
    "default_region": "PL",
    "attributes": ["segment"],
    "columns": {"external_ref": "id"},
}


def test_query_selects_our_names_and_filters_by_since_only_when_given() -> None:
    connector = build("postgres", CONFIG)
    assert isinstance(connector, PostgresConnector)
    full = connector.query(None).as_string()
    assert full.startswith('SELECT "phone" AS "phone", "first_name" AS "first_name"')
    assert '"id" AS "external_ref"' in full and ', "segment" FROM "legacy"."contacts"' in full
    assert "WHERE" not in full and full.endswith('ORDER BY "updated_at"')
    since = connector.query(datetime(2026, 10, 11, tzinfo=UTC)).as_string()
    assert 'WHERE "updated_at" > %(since)s ORDER BY' in since
    assert (
        PostgresConnector(table="contacts_export")
        .query(None)
        .as_string()
        .endswith('FROM "contacts_export" ORDER BY "updated_at"')
    )


def test_map_builds_the_upsert_with_consent_ref_and_attributes() -> None:
    connector = build("postgres", CONFIG)
    record = {
        "phone": "600 100 002",
        "first_name": "Anna",
        "locale": None,
        "country": "PL",
        "external_ref": 2,
        "consent": "opted_in",
        "updated_at": "2026-10-11T10:00:00+00:00",
        "segment": "volunteers",
    }
    upsert = connector.map(record)
    assert (upsert.phone, upsert.first_name, upsert.country) == ("600 100 002", "Anna", "PL")
    assert upsert.external_ref == "postgres:2"
    assert upsert.attributes == {"segment": "volunteers"}
    assert upsert.consent == ConsentChange("opted_in", "postgres", "2026-10-11T10:00:00+00:00")
    no_consent = connector.map({**record, "consent": None, "external_ref": None})
    assert no_consent.consent is None and no_consent.external_ref is None


def test_extract_needs_the_connection_string() -> None:
    connector = PostgresConnector(dsn_env="SYNC_TEST_UNSET_DSN")
    with pytest.raises(RuntimeError, match="SYNC_TEST_UNSET_DSN is not set"):
        list(connector.extract(None))


@pytest.mark.anyio
@pytest.mark.skipif(not os.environ.get("SYNC_POSTGRES_DSN"), reason="needs a source database")
async def test_live_demo_table_syncs_into_a_fake_store() -> None:
    db = FakeDb()
    stats = await run_sync(db, build("postgres", CONFIG), since=None)
    assert stats.extracted == 4 and stats.invalid == 1 and stats.inserted == 3
    phones = sorted(c["phone_e164"] for c in db.rows("contacts"))
    assert phones == ["+48600100001", "+48600100002", "+4915123456789"]
    since = datetime(2026, 10, 12, 12, tzinfo=UTC)
    assert (await run_sync(FakeDb(), build("postgres", CONFIG), since=since)).extracted == 1
