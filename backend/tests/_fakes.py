"""Test doubles shared by the API route tests."""

from typing import Any

from fastapi import HTTPException

Row = dict[str, Any]


class FakeDb:
    """In-memory stand-in for api.db.Database, enough for the routes' needs."""

    def __init__(self) -> None:
        self.tables: dict[str, list[Row]] = {}
        self._next_id = 0

    def rows(self, table: str) -> list[Row]:
        return self.tables.setdefault(table, [])

    async def select(self, table: str, **filters: str) -> list[Row]:
        wanted = {key: value.removeprefix("eq.") for key, value in filters.items()}
        return [r for r in self.rows(table) if all(str(r.get(k)) == v for k, v in wanted.items())]

    async def insert(self, table: str, row: Row) -> Row:
        if table == "templates" and any(
            r["name"] == row["name"] and r["language"] == row["language"] for r in self.rows(table)
        ):
            raise HTTPException(409, "duplicate key value violates unique constraint")
        return self._store(table, row)

    async def update(self, table: str, row_id: str, changes: Row) -> Row:
        for row in self.rows(table):
            if row["id"] == row_id:
                row.update(changes)
                return row
        raise HTTPException(404, f"{table} row not found")

    async def insert_ignore(self, table: str, row: Row, on_conflict: str) -> Row | None:
        if self._find(table, row, on_conflict) is not None:
            return None
        return self._store(table, row)

    async def upsert(self, table: str, row: Row, on_conflict: str) -> Row:
        existing = self._find(table, row, on_conflict)
        if existing is not None:
            existing.update(row)
            return existing
        return self._store(table, row)

    def _find(self, table: str, row: Row, on_conflict: str) -> Row | None:
        keys = on_conflict.split(",")
        for existing in self.rows(table):
            if all(existing.get(key) == row.get(key) for key in keys):
                return existing
        return None

    def _store(self, table: str, row: Row) -> Row:
        self._next_id += 1
        stored = {"id": f"{table}-{self._next_id}", "meta_template_id": None, **row}
        self.rows(table).append(stored)
        return stored
