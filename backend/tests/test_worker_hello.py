"""Worker smoke test on Temporal's time-skipping test server (downloaded on first run)."""

import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from worker.activities.hello import say_hello
from worker.workflows.hello import HelloWorkflow


@pytest.mark.anyio
async def test_hello_workflow_runs_end_to_end() -> None:
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue="test-queue", workflows=[HelloWorkflow], activities=[say_hello]
        ):
            result = await env.client.execute_workflow(
                HelloWorkflow.run, "Ala", id="hello-test-1", task_queue="test-queue"
            )
    assert result == "Hello, Ala!"
