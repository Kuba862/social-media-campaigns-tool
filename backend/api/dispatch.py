"""The API's side of the command queue (decision 41): every Temporal action becomes a row in
dispatch_queue that the worker executes. The API therefore needs no Temporal address or key."""

import uuid
from dataclasses import asdict
from typing import Any

from api.db import Database, Row
from worker.workflows.journey import JourneyRunInput, ReplySignal


class QueuedRuns:
    """Implements api.temporal.AllRuns by enqueueing; `state` and `schedule_info` read the DB."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def start(self, workflow_id: str, run: JourneyRunInput) -> None:
        await self._enqueue("start_run", {"workflow_id": workflow_id, "run": asdict(run)})

    async def cancel(self, workflow_id: str) -> None:
        await self._enqueue("cancel_run", {"workflow_id": workflow_id})

    async def state(self, workflow_id: str) -> dict[str, str]:
        return {}  # live state needs Temporal; the row's current_node_id is what the panel shows

    async def signal_reply(self, workflow_id: str, reply: ReplySignal) -> None:
        await self._signal(workflow_id, "inbound_message", asdict(reply))

    async def signal_opt_out(self, workflow_id: str) -> None:
        await self._signal(workflow_id, "opt_out", None)

    async def signal_status(self, workflow_id: str, status: dict[str, Any]) -> None:
        await self._signal(workflow_id, "message_status", status)

    async def start_sync(self, connector: str) -> str:
        workflow_id = f"sync:{connector}:manual-{uuid.uuid4().hex[:8]}"
        await self._enqueue("start_sync", {"connector": connector, "workflow_id": workflow_id})
        return workflow_id

    async def apply_schedule(self, connector: str, cron: str, enabled: bool) -> None:
        await self._enqueue(
            "apply_schedule", {"connector": connector, "cron": cron, "enabled": enabled}
        )

    async def schedule_info(self, connector: str) -> dict[str, Any] | None:
        rows = await self._db.select("sync_connectors", name=f"eq.{connector}")
        state: dict[str, Any] | None = rows[0].get("schedule_state") if rows else None
        return state

    async def _signal(self, workflow_id: str, name: str, payload: Any) -> None:
        await self._enqueue(
            "signal", {"workflow_id": workflow_id, "name": name, "payload": payload}
        )

    async def _enqueue(self, kind: str, payload: dict[str, Any]) -> Row:
        return await self._db.insert("dispatch_queue", {"kind": kind, "payload": payload})
