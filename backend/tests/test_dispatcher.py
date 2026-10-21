"""The worker's dispatcher executes queued commands on a real Temporal dev server (start_local
supports schedules, which the time-skipping server does not) with FakeDb as the database."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import asdict
from typing import Any

import pytest
from temporalio.client import Client, WorkflowFailureError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from tests._fakes import FakeDb, FakeMeta
from worker.activities.journey import JourneyActivities
from worker.activities.sync import SyncActivities
from worker.dispatch import MAX_ATTEMPTS, Dispatcher
from worker.temporal_runs import TemporalRuns
from worker.workflows.journey import TASK_QUEUE, JourneyRunInput, JourneyWorkflow
from worker.workflows.sync import SyncConnectorWorkflow

PHONE = "+48600000001"
STRAIGHT: dict[str, Any] = {
    "schema_version": 1,
    "nodes": [{"id": "start", "type": "start"}, {"id": "end", "type": "end"}],
    "edges": [{"from": "start", "to": "end"}],
}
ASK: dict[str, Any] = {
    "schema_version": 1,
    "nodes": [
        {"id": "start", "type": "start"},
        {"id": "ask", "type": "wait_for_reply", "timeout": "PT5M"},
        {"id": "end", "type": "end"},
    ],
    "edges": [
        {"from": "start", "to": "ask"},
        {"from": "ask", "to": "end", "port": "replied"},
        {"from": "ask", "to": "end", "port": "timeout"},
    ],
}


def seeded() -> FakeDb:
    db = FakeDb()
    db.rows("contacts").append({"id": "c-1", "phone_e164": PHONE, "attributes": {}})
    db.rows("consents").append(
        {"contact_id": "c-1", "status": "opted_in", "captured_at": "2026-10-01T10:00:00+00:00"}
    )
    db.rows("sync_connectors").append(
        {"id": "sc-1", "name": "fake", "schedule_cron": "0 * * * *", "enabled": True, "config": {}}
    )
    return db


def queue_run(db: FakeDb, run_id: str, definition: dict[str, Any]) -> str:
    workflow_id = f"journey:j-1:contact:c-1:{run_id}"
    db.rows("journey_runs").append(
        {"id": run_id, "workflow_id": workflow_id, "status": "queued", "contact_id": "c-1"}
    )
    run = JourneyRunInput(run_id, "j-1", "v-1", "c-1", definition)
    db.rows("dispatch_queue").append(
        {
            "id": f"q-{run_id}",
            "kind": "start_run",
            "payload": {"workflow_id": workflow_id, "run": asdict(run)},
            "attempts": 0,
            "done_at": None,
        }
    )
    return workflow_id


def enqueue(db: FakeDb, kind: str, payload: dict[str, Any]) -> None:
    db.rows("dispatch_queue").append(
        {
            "id": f"q-{len(db.rows('dispatch_queue')) + 1}",
            "kind": kind,
            "payload": payload,
            "attempts": 0,
            "done_at": None,
        }
    )


@pytest.fixture
async def client() -> AsyncIterator[Client]:
    async with await WorkflowEnvironment.start_local() as env:
        yield env.client


async def running_worker(client: Client, db: FakeDb) -> Worker:
    journey = JourneyActivities(db, FakeMeta(), send_mode="test", allowlist={PHONE})
    return Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[JourneyWorkflow, SyncConnectorWorkflow],
        activities=[*journey.all(), *SyncActivities(db).all()],
    )


@pytest.mark.anyio
async def test_start_run_starts_the_workflow_and_marks_the_row_running(client: Client) -> None:
    db = seeded()
    workflow_id = queue_run(db, "r-1", STRAIGHT)
    dispatcher = Dispatcher(db, TemporalRuns(client))
    async with await running_worker(client, db):
        assert await dispatcher.process_pending() == 1
        assert db.rows("dispatch_queue")[0]["done_at"] is not None
        assert (
            await asyncio.wait_for(client.get_workflow_handle(workflow_id).result(), 20)
            == "completed"
        )
    assert (
        db.rows("journey_runs")[0]["status"] == "completed"
    )  # running, then the workflow's own update
    assert await dispatcher.process_pending() == 0  # nothing left


@pytest.mark.anyio
async def test_signals_and_cancel_reach_the_workflow(client: Client) -> None:
    db = seeded()
    waiting = queue_run(db, "r-1", ASK)
    cancelled = queue_run(db, "r-2", ASK)
    dispatcher = Dispatcher(db, TemporalRuns(client))
    async with await running_worker(client, db):
        await dispatcher.process_pending()
        enqueue(
            db,
            "signal",
            {
                "workflow_id": waiting,
                "name": "inbound_message",
                "payload": {
                    "wamid": "wamid.IN1",
                    "text": "yes",
                    "button_payload": None,
                    "context_wamid": None,
                },
            },
        )
        enqueue(db, "cancel_run", {"workflow_id": cancelled})
        enqueue(
            db, "signal", {"workflow_id": "journey:nope", "name": "opt_out", "payload": None}
        )  # unknown run: ignored
        assert await dispatcher.process_pending() == 3
        assert (
            await asyncio.wait_for(client.get_workflow_handle(waiting).result(), 20) == "completed"
        )
        with pytest.raises(WorkflowFailureError):
            await asyncio.wait_for(client.get_workflow_handle(cancelled).result(), 20)
    assert [row["done_at"] is not None for row in db.rows("dispatch_queue")] == [True] * 5
    assert all(row["error"] is None for row in db.rows("dispatch_queue"))


@pytest.mark.anyio
async def test_sync_start_is_idempotent_and_schedule_state_is_stored(client: Client) -> None:
    db = seeded()
    enqueue(db, "start_sync", {"connector": "fake", "workflow_id": "sync:fake:manual-1"})
    enqueue(db, "start_sync", {"connector": "fake", "workflow_id": "sync:fake:manual-1"})  # a retry
    enqueue(db, "apply_schedule", {"connector": "fake", "cron": "0 * * * *", "enabled": False})
    dispatcher = Dispatcher(db, TemporalRuns(client))
    async with await running_worker(client, db):
        assert await dispatcher.process_pending() == 3
        result = await asyncio.wait_for(
            client.get_workflow_handle("sync:fake:manual-1").result(), 30
        )
    assert result["extracted"] == 4
    assert len(db.rows("sync_runs")) == 1
    state = db.rows("sync_connectors")[0]["schedule_state"]
    assert state["paused"] is True and "applied_at" in state and state["runs"] == 0
    await dispatcher.refresh_schedules()
    assert db.rows("sync_connectors")[0]["schedule_state"]["paused"] is True


@pytest.mark.anyio
async def test_a_bad_command_retries_then_becomes_a_dead_letter(client: Client) -> None:
    db = seeded()
    enqueue(db, "signal", {"workflow_id": "x", "name": "no_such_signal", "payload": None})
    dispatcher = Dispatcher(db, TemporalRuns(client))
    for attempt in range(1, MAX_ATTEMPTS + 1):
        assert await dispatcher.process_pending() == 1
        row = db.rows("dispatch_queue")[0]
        assert row["attempts"] == attempt and "unknown signal" in row["error"]
    assert row["done_at"] is not None
    assert await dispatcher.process_pending() == 0


@pytest.mark.anyio
async def test_reconcile_fixes_rows_temporal_does_not_know_or_has_finished(client: Client) -> None:
    db = seeded()
    finished = queue_run(db, "r-1", STRAIGHT)
    dispatcher = Dispatcher(db, TemporalRuns(client))
    async with await running_worker(client, db):
        await dispatcher.process_pending()
        await asyncio.wait_for(client.get_workflow_handle(finished).result(), 20)
    db.rows("journey_runs")[0]["status"] = "running"  # pretend the worker died before the update
    db.rows("journey_runs").append(
        {"id": "r-lost", "workflow_id": "journey:lost", "status": "running", "contact_id": "c-1"}
    )
    assert await dispatcher.reconcile() == 2
    assert [(r["id"], r["status"]) for r in db.rows("journey_runs")] == [
        ("r-1", "completed"),
        ("r-lost", "failed"),
    ]
    assert all(r["ended_at"].endswith("+00:00") for r in db.rows("journey_runs"))


@pytest.mark.anyio
async def test_a_second_start_for_an_active_workflow_cancels_its_row(client: Client) -> None:
    db = seeded()
    first = queue_run(db, "r-1", ASK)
    db.rows("journey_runs").append(
        {"id": "r-2", "workflow_id": first, "status": "queued", "contact_id": "c-1"}
    )
    run = JourneyRunInput("r-2", "j-1", "v-1", "c-1", ASK)
    enqueue(db, "start_run", {"workflow_id": first, "run": asdict(run)})
    dispatcher = Dispatcher(db, TemporalRuns(client))
    async with await running_worker(client, db):
        assert await dispatcher.process_pending() == 2
        await client.get_workflow_handle(first).cancel()
    assert [(r["id"], r["status"]) for r in db.rows("journey_runs")] == [
        ("r-1", "running"),
        ("r-2", "cancelled"),
    ]
