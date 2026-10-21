"""Supabase REST (PostgREST) with the service role key. Server side only (decision 14)."""

from typing import Any

import httpx
from fastapi import HTTPException, status

from api.settings import Settings

Row = dict[str, Any]


class Database:
    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        self._http = http
        self._base = f"{settings.supabase_url}/rest/v1"
        self._headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Prefer": "return=representation",
        }

    async def select(self, table: str, **filters: str) -> list[Row]:
        """Filters use PostgREST syntax: id="eq.<uuid>", status="eq.DRAFT"."""
        params = {"select": "*", "order": "created_at.desc", **filters}
        return await self._rows("GET", table, params=params)

    async def insert(self, table: str, row: Row) -> Row:
        return (await self._rows("POST", table, json=row))[0]

    async def update(self, table: str, row_id: str, changes: Row) -> Row:
        rows = await self._rows("PATCH", table, params={"id": f"eq.{row_id}"}, json=changes)
        if not rows:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"{table} row not found")
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
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable"
            ) from exc
        if response.status_code == status.HTTP_409_CONFLICT:
            raise HTTPException(status.HTTP_409_CONFLICT, _message(response))
        if not response.is_success:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, _message(response))
        rows: list[Row] = response.json()
        return rows


def _message(response: httpx.Response) -> str:
    try:
        detail = response.json()
    except ValueError:
        return response.text[:200]
    return str(detail.get("message") or detail)
