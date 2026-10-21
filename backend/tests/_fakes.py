"""Test doubles shared by the API route tests."""

from typing import Any

from meta_client import CreatedTemplate, MetaError, SendResult, TemplateSpec, TemplateState
from storage.postgrest import ConflictError, NotFoundError

Row = dict[str, Any]


class FakeDb:
    """In-memory stand-in for api.db.Database, enough for the routes' needs."""

    def __init__(self) -> None:
        self.tables: dict[str, list[Row]] = {}
        self._next_id = 0

    def rows(self, table: str) -> list[Row]:
        return self.tables.setdefault(table, [])

    async def select(self, table: str, columns: str = "*", **filters: str) -> list[Row]:
        wanted = {key: value.removeprefix("eq.") for key, value in filters.items()}
        return [r for r in self.rows(table) if all(str(r.get(k)) == v for k, v in wanted.items())]

    async def insert(self, table: str, row: Row) -> Row:
        if table == "templates" and any(
            r["name"] == row["name"] and r["language"] == row["language"] for r in self.rows(table)
        ):
            raise ConflictError("duplicate key value violates unique constraint")
        return self._store(table, row)

    async def update(self, table: str, row_id: str, changes: Row) -> Row:
        for row in self.rows(table):
            if row["id"] == row_id:
                row.update(changes)
                return row
        raise NotFoundError(f"{table} row not found")

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


class FakeMeta:
    """Stand-in for meta_client.MetaClient with canned answers and switchable failures."""

    def __init__(self) -> None:
        self.create_error: MetaError | None = None
        self.send_error: MetaError | None = None
        self.state: TemplateState | None = TemplateState(meta_template_id="m-1", status="APPROVED")
        self.created: list[TemplateSpec] = []
        self.sent: list[tuple[str, str, str, list[str]]] = []

    async def create_template(self, spec: TemplateSpec) -> CreatedTemplate:
        if self.create_error is not None:
            raise self.create_error
        self.created.append(spec)
        return CreatedTemplate(meta_template_id="m-1", status="PENDING")

    async def get_template_state(self, name: str, language: str) -> TemplateState | None:
        return self.state

    async def send_template(
        self, to_e164: str, template_name: str, language: str, body_values: list[str]
    ) -> SendResult:
        if self.send_error is not None:
            raise self.send_error
        self.sent.append((to_e164, template_name, language, body_values))
        return SendResult(wamid=f"wamid.T{len(self.sent)}", status="accepted")
