"""Executes the API's queued commands on Temporal (decision 41) and reconciles journey_runs
after a worker restart. One poller per worker process; the queue keeps commands in order."""

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import Any

from temporalio.client import WorkflowExecutionStatus

from storage.postgrest import Row, Storage
from worker.temporal_runs import RunAlreadyActive, TemporalRuns
from worker.workflows.journey import JourneyRunInput, ReplySignal

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 5  # then the command is closed with its error (a dead letter), not retried
FROM_TEMPORAL: dict[WorkflowExecutionStatus, str] = {
    WorkflowExecutionStatus.COMPLETED: "completed",
    WorkflowExecutionStatus.FAILED: "failed",
    WorkflowExecutionStatus.CANCELED: "cancelled",
    WorkflowExecutionStatus.TERMINATED: "cancelled",
    WorkflowExecutionStatus.TIMED_OUT: "failed",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Dispatcher:
    def __init__(
        self,
        db: Storage,
        runs: TemporalRuns,
        *,
        poll_interval: float = 2.0,
        schedule_refresh: float = 300.0,
    ) -> None:
        self._db = db
        self._runs = runs
        self._poll_interval = poll_interval
        self._schedule_refresh = schedule_refresh

    async def run_forever(self) -> None:
        fixed = await self.reconcile()
        log.info("dispatcher ready; reconciled %s run(s) after start", fixed)
        last_refresh = time.monotonic()
        while True:
            handled = 0
            try:
                handled = await self.process_pending()
                if time.monotonic() - last_refresh >= self._schedule_refresh:
                    await self.refresh_schedules()
                    last_refresh = time.monotonic()
            except Exception:
                log.exception("dispatcher loop failed; retrying after the poll interval")
            await asyncio.sleep(0 if handled else self._poll_interval)

    async def process_pending(self) -> int:
        """Execute every open command, oldest first; returns how many were attempted."""
        rows = await self._db.select("dispatch_queue", done_at="is.null", order="created_at.asc")
        for row in rows:
            await self._handle(row)
        return len(rows)

    async def _handle(self, row: Row) -> None:
        try:
            await self._execute(str(row["kind"]), dict(row.get("payload") or {}))
        except Exception as exc:
            attempts = int(row.get("attempts") or 0) + 1
            changes: Row = {"attempts": attempts, "error": f"{type(exc).__name__}: {exc}"[:500]}
            if attempts >= MAX_ATTEMPTS:
                changes["done_at"] = _now()
                log.error(
                    "command %s %s gave up after %s attempts", row["id"], row["kind"], attempts
                )
            else:
                log.warning(
                    "command %s %s failed (attempt %s): %s", row["id"], row["kind"], attempts, exc
                )
            await self._db.update("dispatch_queue", row["id"], changes)
            return
        await self._db.update("dispatch_queue", row["id"], {"done_at": _now(), "error": None})

    async def _execute(self, kind: str, payload: dict[str, Any]) -> None:
        if kind == "start_run":
            run = JourneyRunInput(**payload["run"])
            try:
                await self._runs.start(payload["workflow_id"], run)
            except RunAlreadyActive:
                await self._db.update(
                    "journey_runs", run.run_id, {"status": "cancelled", "ended_at": _now()}
                )
                return
            await self._db.update("journey_runs", run.run_id, {"status": "running"})
        elif kind == "cancel_run":
            await self._runs.cancel(payload["workflow_id"])
        elif kind == "signal":
            await self._signal(payload["workflow_id"], payload["name"], payload.get("payload"))
        elif kind == "start_sync":
            await self._runs.start_sync(payload["connector"], payload.get("workflow_id"))
        elif kind == "apply_schedule":
            await self._runs.apply_schedule(
                payload["connector"], payload["cron"], bool(payload["enabled"])
            )
            await self._store_schedule_state(payload["connector"])
        else:
            raise ValueError(f"unknown command kind {kind}")

    async def _signal(self, workflow_id: str, name: str, payload: Any) -> None:
        if name == "inbound_message":
            await self._runs.signal_reply(workflow_id, ReplySignal(**payload))
        elif name == "opt_out":
            await self._runs.signal_opt_out(workflow_id)
        elif name == "message_status":
            await self._runs.signal_status(workflow_id, dict(payload))
        else:
            raise ValueError(f"unknown signal {name}")

    async def _store_schedule_state(self, connector: str) -> None:
        rows = await self._db.select("sync_connectors", name=f"eq.{connector}")
        if not rows:
            return
        info = await self._runs.schedule_info(connector)
        state = {**info, "applied_at": _now()} if info is not None else None
        await self._db.update("sync_connectors", rows[0]["id"], {"schedule_state": state})

    async def refresh_schedules(self) -> None:
        """Keep next_run_at and the run count in the rows fresh for the panel."""
        for row in await self._db.select("sync_connectors"):
            info = await self._runs.schedule_info(row["name"])
            current = row.get("schedule_state") or {}
            if info is None or all(current.get(k) == v for k, v in info.items()):
                continue
            await self._db.update(
                "sync_connectors", row["id"], {"schedule_state": {**current, **info}}
            )

    async def reconcile(self) -> int:
        """Rows the database calls running whose workflow Temporal has finished or never knew.

        A dev server without persistence loses in-flight workflows on restart; those rows
        become failed so the panel stops showing them as running.
        """
        fixed = 0
        for row in await self._db.select("journey_runs", status="eq.running"):
            status = await self._runs.status(row["workflow_id"])
            if status is None:
                new = "failed"
                log.warning("run %s is unknown to Temporal; marking it failed", row["id"])
            elif status in FROM_TEMPORAL:
                new = FROM_TEMPORAL[status]
            else:
                continue
            await self._db.update("journey_runs", row["id"], {"status": new, "ended_at": _now()})
            fixed += 1
        return fixed
