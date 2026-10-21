"""SyncConnectorWorkflow on the time-skipping server with the fake connector and FakeDb."""

from typing import Any

import pytest
from temporalio.client import WorkflowFailureError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from tests._fakes import FakeDb
from worker.activities.sync import SyncActivities
from worker.workflows.sync import SyncConnectorWorkflow

QUEUE = "test-sync"


def seeded(config: dict[str, Any] | None = None) -> tuple[FakeDb, SyncActivities]:
    db = FakeDb()
    db.rows("sync_connectors").append(
        {
            "id": "sc-1",
            "name": "fake",
            "schedule_cron": "0 * * * *",
            "enabled": True,
            "config": config or {},
        }
    )
    return db, SyncActivities(db)


async def run_once(acts: SyncActivities, workflow_id: str) -> dict[str, int]:
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue=QUEUE, workflows=[SyncConnectorWorkflow], activities=acts.all()
        ):
            result: dict[str, int] = await env.client.execute_workflow(
                SyncConnectorWorkflow.run, "fake", id=workflow_id, task_queue=QUEUE
            )
            return result


@pytest.mark.anyio
async def test_a_run_writes_contacts_and_records_its_stats() -> None:
    db, acts = seeded()
    stats = await run_once(acts, "sync:fake:1")
    assert stats == {
        "extracted": 4,
        "inserted": 3,
        "updated": 0,
        "unchanged": 0,
        "consents": 3,
        "invalid": 1,
    }
    run = db.rows("sync_runs")[0]
    assert (run["connector_id"], run["status"], run["stats"]) == ("sc-1", "succeeded", stats)
    assert run["error"] is None and run["ended_at"].endswith("+00:00")
    assert len(db.rows("contacts")) == 3


@pytest.mark.anyio
async def test_the_next_run_starts_where_the_last_successful_one_began() -> None:
    db, acts = seeded()
    await run_once(acts, "sync:fake:1")
    again = await run_once(acts, "sync:fake:2")
    assert again["extracted"] == 0  # the sample's updated_at values are older than run 1
    assert [r["status"] for r in db.rows("sync_runs")] == ["succeeded", "succeeded"]


@pytest.mark.anyio
async def test_a_failing_source_marks_the_run_failed_and_fails_the_workflow() -> None:
    db, acts = seeded({"fail": True})
    with pytest.raises(WorkflowFailureError):
        await run_once(acts, "sync:fake:3")
    run = db.rows("sync_runs")[0]
    assert run["status"] == "failed" and "fake connector failure" in run["error"]
    assert run["stats"] == {}
    assert db.rows("contacts") == []


@pytest.mark.anyio
async def test_an_unknown_connector_fails_before_opening_a_run() -> None:
    db = FakeDb()
    with pytest.raises(WorkflowFailureError):
        await run_once(SyncActivities(db), "sync:fake:4")
    assert db.rows("sync_runs") == []
