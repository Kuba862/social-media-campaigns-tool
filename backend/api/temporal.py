"""The API's door to Temporal: journey runs (guide 4.2) and sync runs with schedules (guide 5)."""

import uuid
from collections.abc import Awaitable
from typing import Any, Protocol

from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleAlreadyRunningError,
    ScheduleSpec,
    ScheduleState,
    ScheduleUpdate,
)
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.service import RPCError, RPCStatusCode

from api.settings import Settings
from worker.workflows.journey import TASK_QUEUE, JourneyRunInput, JourneyWorkflow, ReplySignal
from worker.workflows.sync import SyncConnectorWorkflow


class RunAlreadyActive(Exception):
    """Temporal refused the workflow id because the same run is still going."""


class JourneyRuns(Protocol):
    async def start(self, workflow_id: str, run: JourneyRunInput) -> None: ...
    async def cancel(self, workflow_id: str) -> None: ...
    async def state(self, workflow_id: str) -> dict[str, str]: ...
    async def signal_reply(self, workflow_id: str, reply: ReplySignal) -> None: ...
    async def signal_opt_out(self, workflow_id: str) -> None: ...
    async def signal_status(self, workflow_id: str, status: dict[str, Any]) -> None: ...


class SyncRuns(Protocol):
    async def start_sync(self, connector: str) -> str: ...
    async def apply_schedule(self, connector: str, cron: str, enabled: bool) -> None: ...
    async def schedule_info(self, connector: str) -> dict[str, Any] | None: ...


class AllRuns(JourneyRuns, SyncRuns, Protocol):
    """One Temporal client serves both; the API's dependency hands out this type."""


def schedule_id(connector: str) -> str:
    return f"sync:{connector}"


class TemporalJourneyRuns:
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
        await self._client.get_workflow_handle(workflow_id).cancel()

    async def state(self, workflow_id: str) -> dict[str, str]:
        handle = self._client.get_workflow_handle_for(JourneyWorkflow.run, workflow_id)
        return await handle.query(JourneyWorkflow.current_state)

    async def signal_reply(self, workflow_id: str, reply: ReplySignal) -> None:
        handle = self._client.get_workflow_handle_for(JourneyWorkflow.run, workflow_id)
        await _ignore_closed(handle.signal(JourneyWorkflow.inbound_message, reply))

    async def signal_opt_out(self, workflow_id: str) -> None:
        handle = self._client.get_workflow_handle_for(JourneyWorkflow.run, workflow_id)
        await _ignore_closed(handle.signal(JourneyWorkflow.opt_out))

    async def signal_status(self, workflow_id: str, status: dict[str, Any]) -> None:
        handle = self._client.get_workflow_handle_for(JourneyWorkflow.run, workflow_id)
        await _ignore_closed(handle.signal(JourneyWorkflow.message_status, status))

    async def start_sync(self, connector: str) -> str:
        """An on-demand run next to the scheduled ones; the caller does not wait for it."""
        workflow_id = f"sync:{connector}:manual-{uuid.uuid4().hex[:8]}"
        await self._client.start_workflow(
            SyncConnectorWorkflow.run, connector, id=workflow_id, task_queue=TASK_QUEUE
        )
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
            state=ScheduleState(
                note="managed by POST /sync/connectors/{name}/schedule", paused=not enabled
            ),
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
            "cron": list(description.schedule.spec.cron_expressions),
            "next_run_at": upcoming[0].isoformat() if upcoming else None,
            "runs": description.info.num_actions,
        }


async def _ignore_closed(call: Awaitable[None]) -> None:
    """A signal to a finished or unknown run is not an error for the webhook."""
    try:
        await call
    except RPCError as exc:
        if exc.status != RPCStatusCode.NOT_FOUND:
            raise


async def connect(settings: Settings) -> TemporalJourneyRuns:
    client = await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
        api_key=settings.temporal_api_key or None,
        tls=bool(settings.temporal_api_key),
    )
    return TemporalJourneyRuns(client)
