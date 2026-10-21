"""The part of every sync that no connector writes: phone numbers, upserts, consents, counts."""

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

import phonenumbers

from storage.postgrest import Row, Storage

ConsentStatus = Literal["opted_in", "opted_out"]


@dataclass(frozen=True)
class ConsentChange:
    status: ConsentStatus
    source: str
    captured_at: str | None = None  # ISO 8601; the framework stamps now() when missing


@dataclass(frozen=True)
class ContactUpsert:
    """What a connector knows about one person; None means "do not touch that column"."""

    phone: str  # as the source has it; the framework normalizes it
    first_name: str | None = None
    locale: str | None = None
    country: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)  # merged into contacts.attributes
    external_ref: str | None = None  # the source system's id: the preferred match key
    consent: ConsentChange | None = None


class Connector(Protocol):
    """One module per source. `name` is the key in sync_connectors; config comes from that row."""

    @property
    def name(self) -> str: ...

    @property
    def default_region(self) -> str | None:  # ISO 3166-1 alpha-2 for numbers without a prefix
        ...

    def extract(self, since: datetime | None) -> Iterable[Mapping[str, Any]]: ...
    def map(self, record: Mapping[str, Any]) -> ContactUpsert: ...


@dataclass
class SyncStats:
    extracted: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    consents: int = 0  # consent rows added (a change or the first one)
    invalid: int = 0  # phone numbers that did not parse as valid: skipped, never guessed

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def normalize_phone(raw: str, default_region: str | None = None) -> str | None:
    """E.164 or None. A number without '+' needs default_region; nothing is guessed."""
    try:
        parsed = phonenumbers.parse(raw.strip(), default_region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(parsed):
        return None
    formatted: str = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    return formatted


def map_records(connector: Connector, records: Iterable[Mapping[str, Any]]) -> list[ContactUpsert]:
    return [connector.map(record) for record in records]


async def sync_batch(
    db: Storage,
    upserts: Iterable[ContactUpsert],
    stats: SyncStats,
    *,
    default_region: str | None = None,
) -> None:
    """Write one batch: invalid numbers are counted and skipped, the rest upserted in order."""
    for upsert in upserts:
        phone = normalize_phone(upsert.phone, default_region)
        if phone is None:
            stats.invalid += 1
            continue
        contact = await _upsert_contact(db, upsert, phone, stats)
        if upsert.consent is not None:
            await _record_consent(db, contact, upsert.consent, stats)


async def run_sync(
    db: Storage, connector: Connector, since: datetime | None, batch_size: int = 100
) -> SyncStats:
    """Extract, map and write in batches; the Temporal workflow does the same as activities."""
    stats = SyncStats()
    batch: list[ContactUpsert] = []
    for record in connector.extract(since):
        stats.extracted += 1
        batch.append(connector.map(record))
        if len(batch) >= batch_size:
            await sync_batch(db, batch, stats, default_region=connector.default_region)
            batch = []
    if batch:
        await sync_batch(db, batch, stats, default_region=connector.default_region)
    return stats


async def _upsert_contact(db: Storage, upsert: ContactUpsert, phone: str, stats: SyncStats) -> Row:
    existing = await _find_contact(db, upsert.external_ref, phone)
    desired: Row = {"phone_e164": phone}
    for column in ("first_name", "locale", "country", "external_ref"):
        value = getattr(upsert, column)
        if value is not None:
            desired[column] = value
    if existing is None:
        row = await db.insert("contacts", {**desired, "attributes": dict(upsert.attributes)})
        stats.inserted += 1
        return row
    changes: Row = {k: v for k, v in desired.items() if existing.get(k) != v}
    current = existing.get("attributes") or {}
    merged = {**current, **upsert.attributes}
    if merged != current:
        changes["attributes"] = merged
    if not changes:
        stats.unchanged += 1
        return existing
    row = await db.update("contacts", existing["id"], changes)
    stats.updated += 1
    return row


async def _find_contact(db: Storage, external_ref: str | None, phone: str) -> Row | None:
    """By the source id first (a person may change number), then by number."""
    if external_ref:
        rows = await db.select("contacts", external_ref=f"eq.{external_ref}")
        if rows:
            return rows[0]
    rows = await db.select("contacts", phone_e164=f"eq.{phone}")
    return rows[0] if rows else None


async def _record_consent(
    db: Storage, contact: Row, change: ConsentChange, stats: SyncStats
) -> None:
    """Consents are append-only (guide section 3): add a row only when the status changes."""
    rows = await db.select("consents", contact_id=f"eq.{contact['id']}")
    latest = max(rows, key=lambda c: str(c.get("captured_at", "")), default=None)
    if latest is not None and latest.get("status") == change.status:
        return
    await db.insert(
        "consents",
        {
            "contact_id": contact["id"],
            "status": change.status,
            "source": change.source,
            "captured_at": change.captured_at or datetime.now(UTC).isoformat(),
        },
    )
    stats.consents += 1
