"""The worker's door to Temporal: start, cancel, signal and inspect journey runs, start syncs,
manage schedules. Used by the dispatcher that executes the API's queued commands."""

import uuid
from collections.abc import Awaitable
from typing import Any

from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleAlreadyRunningError,
    ScheduleSpec,
    ScheduleState,
    ScheduleUpdate,
    WorkflowExecutionStatus,
)
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.service import RPCError, RPCStatusCode

from worker.workflows.journey import TASK_QUEUE, JourneyRunInput, JourneyWorkflow, ReplySignal
from worker.workflows.sync import SyncConnectorWorkflow


class RunAlreadyActive(Exception):
    """Temporal refused the workflow id because the same run is still going."""


def schedule_id(connector: str) -> str:
    return f"sync:{connector}"


class TemporalRuns:
    def __init__(self, client: Client) -> None:
        self._client = client

    async def start(self, workflow_id: str, run: JourneyRunInput) -> None:
        try:
            await self._client.start_workflow(
                JourneyWorkflow.run, run, id=workflow_id, task_queue=TASK_QUEUE
            )
        except WorkflowAlreadyStartedError as exc:
            raise RunAlreadyActive(workflow_id) from exc

    async def cancel(self, workflow_id: str) -> None:
        await _ignore_closed(self._client.get_workflow_handle(workflow_id).cancel())

    async def state(self, workflow_id: str) -> dict[str, str]:
        handle = self._client.get_workflow_handle_for(JourneyWorkflow.run, workflow_id)
        return await handle.query(JourneyWorkflow.current_state)

    async def status(self, workflow_id: str) -> WorkflowExecutionStatus | None:
        """Temporal's view of a run, or None when it knows no such workflow."""
        try:
            description = await self._client.get_workflow_handle(workflow_id).describe()
        except RPCError as exc:
            if exc.status == RPCStatusCode.NOT_FOUND:
                return None
            raise
        return description.status

    async def signal_reply(self, workflow_id: str, reply: ReplySignal) -> None:
        handle = self._client.get_workflow_handle_for(JourneyWorkflow.run, workflow_id)
        await _ignore_closed(handle.signal(JourneyWorkflow.inbound_message, reply))

    async def signal_opt_out(self, workflow_id: str) -> None:
        handle = self._client.get_workflow_handle_for(JourneyWorkflow.run, workflow_id)
        await _ignore_closed(handle.signal(JourneyWorkflow.opt_out))

    async def signal_status(self, workflow_id: str, status: dict[str, Any]) -> None:
        handle = self._client.get_workflow_handle_for(JourneyWorkflow.run, workflow_id)
        await _ignore_closed(handle.signal(JourneyWorkflow.message_status, status))

    async def start_sync(self, connector: str, workflow_id: str | None = None) -> str:
        """An on-demand sync; an id given by the queue keeps retries from starting it twice."""
        workflow_id = workflow_id or f"sync:{connector}:manual-{uuid.uuid4().hex[:8]}"
        try:
            await self._client.start_workflow(
                SyncConnectorWorkflow.run, connector, id=workflow_id, task_queue=TASK_QUEUE
            )
        except WorkflowAlreadyStartedError:
            pass
        return workflow_id

    async def apply_schedule(self, connector: str, cron: str, enabled: bool) -> None:
        """Create or replace the connector's schedule; `enabled` false keeps it paused."""
        schedule = Schedule(
            action=ScheduleActionStartWorkflow(
                SyncConnectorWorkflow.run,
                connector,
                id=f"sync:{connector}:scheduled",  # Temporal appends the fire time
                task_queue=TASK_QUEUE,
            ),
            spec=ScheduleSpec(cron_expressions=[cron]),
            state=ScheduleState(note="managed by the worker dispatcher", paused=not enabled),
        )
        try:
            await self._client.create_schedule(schedule_id(connector), schedule)
        except ScheduleAlreadyRunningError:
            handle = self._client.get_schedule_handle(schedule_id(connector))
            await handle.update(lambda _: ScheduleUpdate(schedule=schedule))

    async def schedule_info(self, connector: str) -> dict[str, Any] | None:
        handle = self._client.get_schedule_handle(schedule_id(connector))
        try:
            description = await handle.describe()
        except RPCError as exc:
            if exc.status == RPCStatusCode.NOT_FOUND:
                return None
            raise
        upcoming = description.info.next_action_times
        return {
            "paused": description.schedule.state.paused,
            "next_run_at": upcoming[0].isoformat() if upcoming else None,
            "runs": description.info.num_actions,
        }


async def _ignore_closed(call: Awaitable[None]) -> None:
    """A signal or cancel for a finished or unknown run is not an error."""
    try:
        await call
    except RPCError as exc:
        if exc.status != RPCStatusCode.NOT_FOUND:
            raise
