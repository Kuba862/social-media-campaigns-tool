"""The API's door to Temporal: start, cancel and inspect journey runs (guide 4.2)."""

from typing import Protocol

from temporalio.client import Client
from temporalio.exceptions import WorkflowAlreadyStartedError

from api.settings import Settings
from worker.workflows.journey import TASK_QUEUE, JourneyRunInput, JourneyWorkflow


class RunAlreadyActive(Exception):
    """Temporal refused the workflow id because the same run is still going."""


class JourneyRuns(Protocol):
    async def start(self, workflow_id: str, run: JourneyRunInput) -> None: ...
    async def cancel(self, workflow_id: str) -> None: ...
    async def state(self, workflow_id: str) -> dict[str, str]: ...


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


async def connect(settings: Settings) -> TemporalJourneyRuns:
    client = await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
        api_key=settings.temporal_api_key or None,
        tls=bool(settings.temporal_api_key),
    )
    return TemporalJourneyRuns(client)
