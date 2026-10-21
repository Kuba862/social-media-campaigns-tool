"""A connector with records in memory: for tests, and the first end-to-end demo of a sync."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sync.framework import ConsentChange, ContactUpsert

SAMPLE: list[dict[str, Any]] = [
    {
        "id": "u1",
        "phone": "+48 600 000 001",
        "first_name": "Ala",
        "country": "PL",
        "consent": "opted_in",
        "updated_at": "2026-10-01T10:00:00+00:00",
    },
    {
        "id": "u2",
        "phone": "600 000 002",
        "first_name": "Ola",
        "country": "PL",
        "consent": "opted_in",
        "updated_at": "2026-10-02T10:00:00+00:00",
    },
    {
        "id": "u3",
        "phone": "12345",
        "first_name": "Nobody",
        "country": "PL",
        "consent": "opted_in",
        "updated_at": "2026-10-03T10:00:00+00:00",
    },
    {
        "id": "u4",
        "phone": "+48600000004",
        "first_name": "Ela",
        "country": "PL",
        "consent": "opted_out",
        "updated_at": "2026-10-04T10:00:00+00:00",
    },
]


@dataclass
class FakeConnector:
    name: str = "fake"
    default_region: str | None = "PL"
    records: list[dict[str, Any]] = field(default_factory=lambda: [dict(r) for r in SAMPLE])
    fail: bool = False  # raise from extract, to test the failure path

    def extract(self, since: datetime | None) -> Iterator[Mapping[str, Any]]:
        if self.fail:
            raise RuntimeError("fake connector failure")
        for record in self.records:
            if since is None or datetime.fromisoformat(record["updated_at"]) > since:
                yield record

    def map(self, record: Mapping[str, Any]) -> ContactUpsert:
        consent = (
            ConsentChange(status=record["consent"], source="fake", captured_at=record["updated_at"])
            if record.get("consent")
            else None
        )
        return ContactUpsert(
            phone=record["phone"],
            first_name=record.get("first_name"),
            country=record.get("country"),
            attributes={"source": "fake"},
            external_ref=f"fake:{record['id']}",
            consent=consent,
        )
