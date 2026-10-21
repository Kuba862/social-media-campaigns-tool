"""Signals on the guide's section 4.1 journey: reply before timeout, timeout, opt-out."""

import asyncio
from datetime import timedelta
from typing import Any

import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from tests._fakes import FakeDb, FakeMeta
from worker.activities.journey import JourneyActivities
from worker.workflows.journey import JourneyRunInput, JourneyWorkflow, ReplySignal

PHONE = "+48600000001"
WORKFLOW_ID = "journey:j-1:contact:c-1"
QUEUE = "test-journeys"


def seeded() -> tuple[FakeDb, FakeMeta, JourneyActivities]:
    db, meta = FakeDb(), FakeMeta()
    db.rows("contacts").append(
        {"id": "c-1", "phone_e164": PHONE, "first_name": "Ala", "attributes": {}}
    )
    db.rows("templates").append(
        {"id": "tpl-1", "name": "welcome_offer", "language": "pl", "status": "APPROVED"}
    )
    db.rows("journey_runs").append({"id": "r-1", "status": "running", "current_node_id": "start"})
    db.rows("consents").append(
        {"contact_id": "c-1", "status": "opted_in", "captured_at": "2026-10-01T10:00:00+00:00"}
    )
    return db, meta, JourneyActivities(db, meta, send_mode="test", allowlist={PHONE})


async def wait_until_waiting_for_reply(handle: Any) -> None:
    for _ in range(100):
        state = await handle.query(JourneyWorkflow.current_state)
        if state["waiting"] == "reply":
            return
        await asyncio.sleep(0.05)
    raise AssertionError("workflow never reached wait_for_reply")


@pytest.mark.anyio
async def test_button_reply_before_timeout_takes_the_replied_port(
    guide_example_json: dict[str, Any],
) -> None:
    db, meta, acts = seeded()
    run = JourneyRunInput("r-1", "j-1", "v-1", "c-1", guide_example_json)
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue=QUEUE, workflows=[JourneyWorkflow], activities=acts.all()
        ):
            handle = await env.client.start_workflow(
                JourneyWorkflow.run, run, id=WORKFLOW_ID, task_queue=QUEUE
            )
            await env.sleep(timedelta(days=2))  # through the wait node, into wait_for_reply
            await wait_until_waiting_for_reply(handle)
            assert (await handle.query(JourneyWorkflow.current_state))["node_id"] == "n3"
            await handle.signal(
                JourneyWorkflow.inbound_message,
                ReplySignal(wamid="wamid.IN1", button_payload="YES", context_wamid="wamid.T1"),
            )
            assert await handle.result() == "completed"
    assert len(meta.sent) == 1
    assert db.rows("contacts")[0]["attributes"] == {"interested": True}
    assert db.rows("journey_runs")[0]["current_node_id"] == "end"


@pytest.mark.anyio
async def test_no_reply_takes_the_timeout_port(guide_example_json: dict[str, Any]) -> None:
    db, meta, acts = seeded()
    run = JourneyRunInput("r-1", "j-1", "v-1", "c-1", guide_example_json)
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue=QUEUE, workflows=[JourneyWorkflow], activities=acts.all()
        ):
            status = await env.client.execute_workflow(
                JourneyWorkflow.run, run, id=WORKFLOW_ID, task_queue=QUEUE
            )
    assert status == "completed"
    assert len(meta.sent) == 1
    assert db.rows("contacts")[0]["attributes"] == {}  # n5 was skipped


@pytest.mark.anyio
async def test_text_reply_without_button_takes_the_else_branch(
    guide_example_json: dict[str, Any],
) -> None:
    db, meta, acts = seeded()
    run = JourneyRunInput("r-1", "j-1", "v-1", "c-1", guide_example_json)
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue=QUEUE, workflows=[JourneyWorkflow], activities=acts.all()
        ):
            status = await env.client.execute_workflow(
                JourneyWorkflow.run,
                run,
                id=WORKFLOW_ID,
                task_queue=QUEUE,
                start_signal="inbound_message",
                start_signal_args=[ReplySignal(wamid="wamid.IN1", text="maybe later")],
            )
    assert status == "completed"
    assert db.rows("contacts")[0]["attributes"] == {}


@pytest.mark.anyio
async def test_opt_out_during_a_wait_ends_the_run_at_once(
    guide_example_json: dict[str, Any],
) -> None:
    db, meta, acts = seeded()
    run = JourneyRunInput("r-1", "j-1", "v-1", "c-1", guide_example_json)
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue=QUEUE, workflows=[JourneyWorkflow], activities=acts.all()
        ):
            handle = await env.client.start_workflow(
                JourneyWorkflow.run, run, id=WORKFLOW_ID, task_queue=QUEUE
            )
            await env.sleep(timedelta(days=1))  # inside the two-day wait
            await handle.signal(JourneyWorkflow.opt_out)
            assert await handle.result() == "opted_out"
    assert len(meta.sent) == 1
    run_row = db.rows("journey_runs")[0]
    assert (run_row["status"], run_row["current_node_id"]) == ("opted_out", "n2")
    assert run_row["ended_at"].endswith("+00:00")


@pytest.mark.anyio
async def test_opt_out_before_the_first_send_sends_nothing(
    guide_example_json: dict[str, Any],
) -> None:
    db, meta, acts = seeded()
    run = JourneyRunInput("r-1", "j-1", "v-1", "c-1", guide_example_json)
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue=QUEUE, workflows=[JourneyWorkflow], activities=acts.all()
        ):
            status = await env.client.execute_workflow(
                JourneyWorkflow.run,
                run,
                id=WORKFLOW_ID,
                task_queue=QUEUE,
                start_signal="opt_out",
                start_signal_args=[],
            )
    assert status == "opted_out"
    assert meta.sent == [] and db.rows("messages") == []
