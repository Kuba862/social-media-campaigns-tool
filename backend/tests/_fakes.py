"""Test doubles shared by the API route tests and the worker tests."""

from typing import Any

from meta_client import (
    CreatedTemplate,
    MetaError,
    MetaTransientError,
    SendResult,
    TemplateSpec,
    TemplateState,
)
from storage.postgrest import ConflictError, NotFoundError, StorageUnavailable
from worker.temporal_runs import RunAlreadyActive
from worker.workflows.journey import JourneyRunInput, ReplySignal

Row = dict[str, Any]


class FakeDb:
    """In-memory stand-in for storage.postgrest.PostgrestClient, enough for the callers' needs."""

    def __init__(self) -> None:
        self.tables: dict[str, list[Row]] = {}
        self.lost_responses: dict[str, int] = {}  # table -> updates that commit, then "time out"
        self._next_id = 0

    def rows(self, table: str) -> list[Row]:
        return self.tables.setdefault(table, [])

    async def select(self, table: str, columns: str = "*", **filters: str) -> list[Row]:
        """PostgREST filters as the callers use them: eq.<value> and in.("a","b")."""

        def matches(row: Row) -> bool:
            for key, value in filters.items():
                if key in ("order", "limit"):
                    continue
                if value == "is.null":
                    if row.get(key) is not None:
                        return False
                elif value.startswith("in.("):
                    wanted = [item.strip('"') for item in value[4:-1].split(",")]
                    if str(row.get(key)) not in wanted:
                        return False
                elif str(row.get(key)) != value.removeprefix("eq."):
                    return False
            return True

        return [r for r in self.rows(table) if matches(r)]

    async def insert(self, table: str, row: Row) -> Row:
        if table == "templates" and any(
            r["name"] == row["name"] and r["language"] == row["language"] for r in self.rows(table)
        ):
            raise ConflictError("duplicate key value violates unique constraint")
        if table == "journey_runs" and any(
            r["journey_id"] == row["journey_id"]
            and r["contact_id"] == row["contact_id"]
            and r["status"] in ("queued", "running")
            for r in self.rows(table)
        ):
            raise ConflictError("duplicate key value violates unique constraint")
        if table == "journey_versions" and any(
            r["journey_id"] == row["journey_id"] and r.get("published_at") is None
            for r in self.rows(table)
        ):
            raise ConflictError("duplicate key value violates unique constraint")
        return self._store(table, row)

    async def update(self, table: str, row_id: str, changes: Row) -> Row:
        for row in self.rows(table):
            if row["id"] == row_id:
                row.update(changes)
                if self.lost_responses.get(table, 0) > 0:
                    self.lost_responses[table] -= 1
                    raise StorageUnavailable("response lost after the write")
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

    async def delete(self, table: str, row_id: str) -> None:
        rows = self.rows(table)
        for index, row in enumerate(rows):
            if row["id"] == row_id:
                del rows[index]
                return
        raise NotFoundError(f"{table} row not found")

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
        self.transient_failures = 0  # how many send attempts fail with a transient error first
        self.state: TemplateState | None = TemplateState(meta_template_id="m-1", status="APPROVED")
        self.created: list[TemplateSpec] = []
        self.created_handles: list[str | None] = []
        self.uploads: list[tuple[str, int]] = []  # (mime, size) of samples sent for image headers
        self.deleted: list[tuple[str, str | None]] = []
        self.sent_headers: list[str | None] = []  # header image url of each template send
        self.sent: list[tuple[str, str, str, list[str]]] = []
        self.sent_texts: list[tuple[str, str]] = []

    async def create_template(
        self, spec: TemplateSpec, header_handle: str | None = None
    ) -> CreatedTemplate:
        if self.create_error is not None:
            raise self.create_error
        self.created.append(spec)
        self.created_handles.append(header_handle)
        return CreatedTemplate(meta_template_id="m-1", status="PENDING")

    async def upload_sample(self, data: bytes, mime: str, file_name: str) -> str:
        self.uploads.append((mime, len(data)))
        return "4::sample-handle"

    async def get_template_state(self, name: str, language: str) -> TemplateState | None:
        return self.state

    async def send_template(
        self,
        to_e164: str,
        template_name: str,
        language: str,
        body_values: list[str],
        header_image_url: str | None = None,
    ) -> SendResult:
        if self.transient_failures > 0:
            self.transient_failures -= 1
            raise MetaTransientError("Meta 400: (#130429) Rate limit hit", code=130429)
        if self.send_error is not None:
            raise self.send_error
        self.sent.append((to_e164, template_name, language, body_values))
        self.sent_headers.append(header_image_url)
        wamid = f"wamid.T{len(self.sent)}"
        return SendResult(wamid=wamid, status="accepted", raw={"messages": [{"id": wamid}]})

    async def delete_template(self, name: str, meta_template_id: str | None = None) -> None:
        self.deleted.append((name, meta_template_id))

    async def send_text(self, to_e164: str, text: str) -> SendResult:
        if self.transient_failures > 0:
            self.transient_failures -= 1
            raise MetaTransientError("Meta 400: (#130429) Rate limit hit", code=130429)
        if self.send_error is not None:
            raise self.send_error
        self.sent_texts.append((to_e164, text))
        wamid = f"wamid.X{len(self.sent_texts)}"
        return SendResult(wamid=wamid, status="accepted", raw={"messages": [{"id": wamid}]})


class FakeTemporal:
    """Stand-in for api.temporal.TemporalJourneyRuns: records starts, cancels and signals."""

    def __init__(self) -> None:
        self.started: list[tuple[str, JourneyRunInput]] = []
        self.cancelled: list[str] = []
        self.active: set[str] = set()
        self.signals: list[tuple[str, str, object]] = []  # (workflow_id, signal name, payload)
        self.sync_started: list[str] = []
        self.schedules: dict[str, tuple[str, bool]] = {}  # connector -> (cron, enabled)

    async def start(self, workflow_id: str, run: JourneyRunInput) -> None:
        if workflow_id in self.active:
            raise RunAlreadyActive(workflow_id)
        self.active.add(workflow_id)
        self.started.append((workflow_id, run))

    async def cancel(self, workflow_id: str) -> None:
        self.cancelled.append(workflow_id)
        self.active.discard(workflow_id)

    async def state(self, workflow_id: str) -> dict[str, str]:
        return {"node_id": "n2", "waiting": "sleep"}

    async def signal_reply(self, workflow_id: str, reply: ReplySignal) -> None:
        self.signals.append((workflow_id, "inbound_message", reply))

    async def signal_opt_out(self, workflow_id: str) -> None:
        self.signals.append((workflow_id, "opt_out", None))

    async def signal_status(self, workflow_id: str, status: dict[str, Any]) -> None:
        self.signals.append((workflow_id, "message_status", status))

    async def start_sync(self, connector: str) -> str:
        workflow_id = f"sync:{connector}:manual-{len(self.sync_started) + 1}"
        self.sync_started.append(workflow_id)
        return workflow_id

    async def apply_schedule(self, connector: str, cron: str, enabled: bool) -> None:
        self.schedules[connector] = (cron, enabled)

    async def schedule_info(self, connector: str) -> dict[str, Any] | None:
        if connector not in self.schedules:
            return None
        _, enabled = self.schedules[connector]
        return {"paused": not enabled, "next_run_at": "2026-10-22T00:00:00+00:00", "runs": 0}
