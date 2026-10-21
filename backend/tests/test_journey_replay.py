"""Acceptance "worker restart": a recorded history must replay on the current workflow code."""

import json

import pytest
from temporalio import workflow
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer
from temporalio.workflow import NondeterminismError

from tests.record_replay_history import HISTORY
from tests.test_journey_signals import WORKFLOW_ID
from worker.workflows.journey import JourneyRunInput, JourneyWorkflow


@workflow.defn(name="JourneyWorkflow", sandboxed=False)
class ReorderedJourneyWorkflow(JourneyWorkflow):
    """The same workflow with one extra command first: what an unguarded code change looks like."""

    @workflow.run
    async def run(self, run: JourneyRunInput) -> str:
        await workflow.sleep(1)
        return await super().run(run)


def recorded() -> WorkflowHistory:
    return WorkflowHistory.from_json(WORKFLOW_ID, HISTORY.read_text())


def test_the_recording_is_the_answered_guide_journey() -> None:
    events = json.loads(HISTORY.read_text())["events"]
    kinds = [e["eventType"].removeprefix("EVENT_TYPE_") for e in events]
    assert kinds.count("WORKFLOW_EXECUTION_SIGNALED") == 1
    assert kinds.count("TIMER_FIRED") == 1 and kinds.count("TIMER_CANCELED") == 1
    assert kinds[-1] == "WORKFLOW_EXECUTION_COMPLETED"


@pytest.mark.anyio
async def test_current_code_replays_the_recorded_history() -> None:
    """A worker restarted on this code resumes the old run; Replayer raises on nondeterminism."""
    await Replayer(workflows=[JourneyWorkflow]).replay_workflow(recorded())


@pytest.mark.anyio
async def test_a_changed_command_order_fails_the_replay() -> None:
    with pytest.raises(NondeterminismError):
        await Replayer(workflows=[ReorderedJourneyWorkflow]).replay_workflow(recorded())
