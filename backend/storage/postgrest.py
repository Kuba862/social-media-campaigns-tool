"""Supabase REST (PostgREST) client shared by the API and the worker (decision 14, decision 20)."""

from typing import Any, Protocol

import httpx

Row = dict[str, Any]


class Storage(Protocol):
    """What callers need from storage; PostgrestClient and the test double both satisfy it."""

    async def select(self, table: str, columns: str = "*", **filters: str) -> list[Row]: ...
    async def insert(self, table: str, row: Row) -> Row: ...
    async def update(self, table: str, row_id: str, changes: Row) -> Row: ...
    async def insert_ignore(self, table: str, row: Row, on_conflict: str) -> Row | None: ...
    async def upsert(self, table: str, row: Row, on_conflict: str) -> Row: ...


class StorageError(Exception):
    """Base class; `transient` tells the caller whether the same call may succeed later."""

    transient = False


class StorageUnavailable(StorageError):
    """No connection to PostgREST."""

    transient = True


class StorageRequestError(StorageError):
    """PostgREST answered with an error other than a conflict; 5xx counts as transient."""

    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status = status
        self.transient = status >= 500


class ConflictError(StorageError):
    """A unique constraint rejected the row."""


class NotFoundError(StorageError):
    """No row matched."""


class PostgrestClient:
    def __init__(
        self, http: httpx.AsyncClient, *, supabase_url: str, service_role_key: str
    ) -> None:
        self._http = http
        self._base = f"{supabase_url.rstrip('/')}/rest/v1"
        self._headers = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Prefer": "return=representation",
        }

    async def select(self, table: str, columns: str = "*", **filters: str) -> list[Row]:
        """PostgREST filters: id="eq.<uuid>"; columns may embed FK tables: "*,templates(name)"."""
        params = {"select": columns, "order": "created_at.desc", **filters}
        return await self._rows("GET", table, params=params)

    async def insert(self, table: str, row: Row) -> Row:
        return (await self._rows("POST", table, json=row))[0]

    async def update(self, table: str, row_id: str, changes: Row) -> Row:
        rows = await self._rows("PATCH", table, params={"id": f"eq.{row_id}"}, json=changes)
        if not rows:
            raise NotFoundError(f"{table} row not found")
        return rows[0]

    async def insert_ignore(self, table: str, row: Row, on_conflict: str) -> Row | None:
        """ON CONFLICT DO NOTHING: the stored row, or None when a duplicate was skipped."""
        rows = await self._rows(
            "POST",
            table,
            params={"on_conflict": on_conflict},
            json=row,
            prefer="resolution=ignore-duplicates,return=representation",
        )
        return rows[0] if rows else None

    async def upsert(self, table: str, row: Row, on_conflict: str) -> Row:
        """Insert, or update the row that shares the conflict columns; returns it as stored."""
        rows = await self._rows(
            "POST",
            table,
            params={"on_conflict": on_conflict},
            json=row,
            prefer="resolution=merge-duplicates,return=representation",
        )
        return rows[0]

    async def _rows(
        self,
        method: str,
        table: str,
        *,
        params: dict[str, str] | None = None,
        json: Row | None = None,
        prefer: str | None = None,
    ) -> list[Row]:
        headers = {**self._headers, "Prefer": prefer} if prefer else self._headers
        try:
            response = await self._http.request(
                method, f"{self._base}/{table}", params=params, json=json, headers=headers
            )
        except httpx.HTTPError as exc:
            raise StorageUnavailable("database unavailable") from exc
        if response.status_code == 409:
            raise ConflictError(_message(response))
        if not response.is_success:
            raise StorageRequestError(_message(response), response.status_code)
        rows: list[Row] = response.json()
        return rows


def _message(response: httpx.Response) -> str:
    try:
        detail = response.json()
    except ValueError:
        return response.text[:200]
    return str(detail.get("message") or detail)
