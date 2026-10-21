"""A connector that reads one table or view in a Postgres database we own (e.g. a legacy CRM).

Configuration lives in sync_connectors.config without secrets; the connection string comes from
the environment variable named by `dsn_env` (Secret Manager secret sync-postgres-dsn in prod).
"""

import os
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from sync.framework import ConsentChange, ContactUpsert

# Our field -> source column. Only `phone` is required; the rest may be missing in the source.
DEFAULT_COLUMNS: dict[str, str] = {
    "phone": "phone",
    "first_name": "first_name",
    "locale": "locale",
    "country": "country",
    "external_ref": "id",
    "consent": "consent",  # 'opted_in' | 'opted_out' | NULL
    "updated_at": "updated_at",  # drives `since`
}


@dataclass(frozen=True)
class PostgresConnector:
    name: str = "postgres"
    default_region: str | None = None
    table: str = "public.contacts_export"  # "schema.table" or "table"
    columns: Mapping[str, str] = field(default_factory=lambda: dict(DEFAULT_COLUMNS))
    attributes: tuple[str, ...] = ()  # extra source columns copied into contacts.attributes
    dsn_env: str = "SYNC_POSTGRES_DSN"

    def query(self, since: datetime | None) -> sql.Composed:
        """SELECT columns AS our names FROM table [WHERE updated_at > since] ORDER BY updated_at."""
        selected = [
            sql.SQL("{} AS {}").format(sql.Identifier(column), sql.Identifier(name))
            for name, column in self.columns.items()
        ] + [sql.Identifier(column) for column in self.attributes]
        parts = [sql.SQL("SELECT {} FROM {}").format(sql.SQL(", ").join(selected), self._table())]
        updated = sql.Identifier(self.columns["updated_at"])
        if since is not None:
            parts.append(sql.SQL("WHERE {} > %(since)s").format(updated))
        parts.append(sql.SQL("ORDER BY {}").format(updated))
        return sql.SQL(" ").join(parts)

    def extract(self, since: datetime | None) -> Iterator[Mapping[str, Any]]:
        dsn = os.environ.get(self.dsn_env, "")
        if not dsn:
            raise RuntimeError(f"{self.dsn_env} is not set")
        with psycopg.connect(dsn) as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(self.query(since), {"since": since})
            for row in cur:
                yield {key: _plain(value) for key, value in row.items()}

    def map(self, record: Mapping[str, Any]) -> ContactUpsert:
        consent_status = record.get("consent")
        consent = (
            ConsentChange(
                status=consent_status, source=self.name, captured_at=record.get("updated_at")
            )
            if consent_status in ("opted_in", "opted_out")
            else None
        )
        ref = record.get("external_ref")
        return ContactUpsert(
            phone=str(record["phone"]),
            first_name=record.get("first_name"),
            locale=record.get("locale"),
            country=record.get("country"),
            attributes={key: record[key] for key in self.attributes if key in record},
            external_ref=f"{self.name}:{ref}" if ref is not None else None,
            consent=consent,
        )

    def _table(self) -> sql.Composable:
        schema, _, table = self.table.partition(".")
        if table:
            return sql.Identifier(schema, table)
        return sql.Identifier(schema)


def _plain(value: Any) -> Any:
    """Rows travel through Temporal as JSON: timestamps become ISO strings, UUIDs strings."""
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)
