"""Record the history of one finished run for the replay test (acceptance: worker restart).

Run from backend/ after an intended change to JourneyWorkflow's command order (guide 4.2 asks
for workflow.patched() plus a fresh recording for each released version):

    uv run python -m tests.record_replay_history
"""

import asyncio
import json
from datetime import timedelta
from pathlib import Path

from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from tests.test_journey_signals import QUEUE, WORKFLOW_ID, seeded, wait_until_waiting_for_reply
from worker.workflows.journey import JourneyRunInput, JourneyWorkflow, ReplySignal

FIXTURES = Path(__file__).parent / "fixtures"
HISTORY = FIXTURES / "temporal" / "journey_guide_example_history.json"


async def record() -> str:
    """Guide 4.1 journey answered with a button: activities, timer, signal, cancelled timer."""
    definition = json.loads((FIXTURES / "journey_guide_example.json").read_text())
    _, _, acts = seeded()
    run = JourneyRunInput("r-1", "j-1", "v-1", "c-1", definition)
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue=QUEUE, workflows=[JourneyWorkflow], activities=acts.all()
        ):
            handle = await env.client.start_workflow(
                JourneyWorkflow.run, run, id=WORKFLOW_ID, task_queue=QUEUE
            )
            await env.sleep(timedelta(days=2))
            await wait_until_waiting_for_reply(handle)
            yes = ReplySignal(wamid="wamid.IN1", button_payload="YES", context_wamid="wamid.T1")
            await handle.signal(JourneyWorkflow.inbound_message, yes)
            assert await handle.result() == "completed"
            history = await handle.fetch_history()
    return history.to_json()


if __name__ == "__main__":
    HISTORY.parent.mkdir(exist_ok=True)
    HISTORY.write_text(asyncio.run(record()))
    print(f"wrote {HISTORY}")
