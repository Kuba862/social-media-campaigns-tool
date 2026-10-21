"""JourneyWorkflow on Temporal's time-skipping test server with fake storage and fake Meta."""

from typing import Any

import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from tests._fakes import FakeDb, FakeMeta
from worker.activities.journey import JourneyActivities
from worker.workflows.journey import JourneyRunInput, JourneyWorkflow

PHONE = "+48600000001"
WORKFLOW_ID = "journey:j-1:contact:c-1"

DEFINITION: dict[str, Any] = {
    "schema_version": 1,
    "nodes": [
        {"id": "start", "type": "start"},
        {
            "id": "hello",
            "type": "send_template",
            "template_id": "t-1",
            "variables": {"1": "contact.first_name"},
        },
        {"id": "pause", "type": "wait", "duration": "P2D"},
        {"id": "mark", "type": "update_contact", "set": {"attributes.greeted": "yes"}},
        {
            "id": "split",
            "type": "branch",
            "conditions": [{"if": {"contact.attributes.greeted": "yes"}, "next": "bye"}],
            "else": "end",
        },
        {"id": "bye", "type": "send_template", "template_id": "t-1", "variables": {}},
        {"id": "end", "type": "end"},
    ],
    "edges": [
        {"from": "start", "to": "hello"},
        {"from": "hello", "to": "pause"},
        {"from": "pause", "to": "mark"},
        {"from": "mark", "to": "split"},
        {"from": "bye", "to": "end"},
    ],
}


def seeded() -> tuple[FakeDb, FakeMeta, JourneyActivities]:
    db, meta = FakeDb(), FakeMeta()
    db.rows("contacts").append(
        {"id": "c-1", "phone_e164": PHONE, "first_name": "Ala", "attributes": {}}
    )
    db.rows("templates").append(
        {"id": "t-1", "name": "welcome_offer", "language": "pl", "status": "APPROVED"}
    )
    db.rows("journey_runs").append({"id": "r-1", "status": "running", "current_node_id": "start"})
    db.rows("consents").append(
        {"contact_id": "c-1", "status": "opted_in", "captured_at": "2026-10-01T10:00:00+00:00"}
    )
    return db, meta, JourneyActivities(db, meta, send_mode="test", allowlist={PHONE})


async def run_journey(acts: JourneyActivities, definition: dict[str, Any] = DEFINITION) -> str:
    run = JourneyRunInput("r-1", "j-1", "v-1", "c-1", definition)
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-journeys",
            workflows=[JourneyWorkflow],
            activities=acts.all(),
        ):
            handle = await env.client.start_workflow(
                JourneyWorkflow.run, run, id=WORKFLOW_ID, task_queue="test-journeys"
            )
            status: str = await handle.result()
            state = await handle.query(JourneyWorkflow.current_state)
            assert state["node_id"] == acts_last_node(status)
            return status


def acts_last_node(status: str) -> str:
    return {"completed": "end", "skipped_no_consent": "hello", "failed": "hello"}[status]


@pytest.mark.anyio
async def test_happy_path_sends_waits_updates_and_branches() -> None:
    db, meta, acts = seeded()
    assert await run_journey(acts) == "completed"
    assert [sent[3] for sent in meta.sent] == [["Ala"], []]  # hello with the name, bye without
    assert db.rows("contacts")[0]["attributes"] == {"greeted": "yes"}
    run = db.rows("journey_runs")[0]
    assert (run["status"], run["current_node_id"]) == ("completed", "end")
    assert run["ended_at"].endswith("+00:00")
    keys = [m["idempotency_key"] for m in db.rows("messages")]
    assert keys == [f"{WORKFLOW_ID}:hello:1", f"{WORKFLOW_ID}:bye:1"]


@pytest.mark.anyio
async def test_no_consent_skips_the_run_before_any_send() -> None:
    db, meta, acts = seeded()
    db.rows("consents").clear()
    assert await run_journey(acts) == "skipped_no_consent"
    assert meta.sent == [] and db.rows("messages") == []
    assert db.rows("journey_runs")[0]["status"] == "skipped_no_consent"


@pytest.mark.anyio
async def test_failed_send_ends_the_run_as_failed() -> None:
    db, meta, acts = seeded()
    db.rows("templates")[0]["status"] = "PENDING"
    assert await run_journey(acts) == "failed"
    assert meta.sent == []
    assert db.rows("messages")[0]["status"] == "failed"
    assert db.rows("journey_runs")[0]["status"] == "failed"


@pytest.mark.anyio
async def test_transient_meta_error_is_retried_without_a_second_send() -> None:
    db, meta, acts = seeded()
    meta.transient_failures = 1
    assert await run_journey(acts) == "completed"
    assert len(meta.sent) == 2  # the failed attempt never reached Meta's "sent" list
    assert [m["status"] for m in db.rows("messages")] == ["sent", "sent"]


@pytest.mark.anyio
async def test_branch_takes_else_when_no_condition_matches() -> None:
    db, meta, acts = seeded()
    definition = {**DEFINITION, "nodes": [dict(node) for node in DEFINITION["nodes"]]}
    definition["nodes"][4] = {
        **definition["nodes"][4],
        "conditions": [{"if": {"contact.attributes.greeted": "no"}, "next": "bye"}],
    }
    assert await run_journey(acts, definition) == "completed"
    assert len(meta.sent) == 1  # bye was skipped
