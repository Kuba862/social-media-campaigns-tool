"""The API writes commands to dispatch_queue instead of calling Temporal (decision 41)."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.auth import AuthUser, current_user
from api.deps import get_db
from api.dispatch import QueuedRuns
from api.main import app
from tests._fakes import FakeDb
from tests.test_webhooks_api import HANDSHAKE, SECRET, VERIFY_TOKEN, body, seed_runs, signed


@pytest.fixture
def db() -> FakeDb:
    db = FakeDb()
    db.rows("templates").append(
        {"id": "tpl-1", "name": "welcome_offer", "language": "pl", "status": "APPROVED"}
    )
    db.rows("contacts").append({"id": "c-1", "phone_e164": "+48600000001"})
    return db


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, db: FakeDb) -> Iterator[TestClient]:
    """Only the database is faked: the real QueuedRuns runs behind every route."""
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.test")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key-for-tests")
    monkeypatch.setenv("PANEL_ALLOWED_EMAIL_DOMAIN", "example.org")
    monkeypatch.setenv("META_APP_SECRET", SECRET)
    monkeypatch.setenv("META_WEBHOOK_VERIFY_TOKEN", VERIFY_TOKEN)
    app.dependency_overrides[current_user] = lambda: AuthUser(id="user-1", email="ala@example.org")
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def queued(db: FakeDb) -> list[tuple[str, dict[str, Any]]]:
    return [(row["kind"], row["payload"]) for row in db.rows("dispatch_queue")]


def test_starting_and_cancelling_runs_enqueues_commands(
    client: TestClient, db: FakeDb, guide_example_json: dict[str, Any]
) -> None:
    journey_id = client.post("/journeys", json={"name": "welcome"}).json()["id"]
    client.post(f"/journeys/{journey_id}/versions", json=guide_example_json)
    started = client.post(f"/journeys/{journey_id}/runs", json={"contact_ids": ["c-1"]}).json()
    run_id = started["started"][0]
    assert db.rows("journey_runs")[0]["status"] == "queued"
    kind, payload = queued(db)[0]
    assert kind == "start_run" and payload["workflow_id"] == f"journey:{journey_id}:contact:c-1"
    assert payload["run"]["run_id"] == run_id and payload["run"]["definition"] == guide_example_json
    again = client.post(f"/journeys/{journey_id}/runs", json={"contact_ids": ["c-1"]}).json()
    assert again["skipped"] == ["c-1"]  # queued counts as active
    assert "live" not in client.get(f"/runs/{run_id}").json()  # nothing to query yet
    cancelled = client.post(f"/runs/{run_id}/cancel")
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    assert queued(db)[1] == ("cancel_run", {"workflow_id": f"journey:{journey_id}:contact:c-1"})


def test_webhook_signals_become_queued_commands(client: TestClient, db: FakeDb) -> None:
    seed_runs(db)
    raw = body("webhook_inbound.json")
    assert client.post("/webhooks/meta", content=raw, headers=signed(raw)).status_code == 200
    names = [(p["workflow_id"], p["name"]) for k, p in queued(db) if k == "signal"]
    assert names == [
        ("wf-1", "inbound_message"),
        ("wf-2", "inbound_message"),
        ("wf-1", "opt_out"),
        ("wf-2", "opt_out"),
        ("wf-1", "inbound_message"),
    ]
    assert queued(db)[0][1]["payload"] == {
        "wamid": "wamid.IN1",
        "text": "STOP",
        "button_payload": None,
        "context_wamid": None,
    }
    assert client.get("/webhooks/meta", params=HANDSHAKE).status_code == 200


def test_sync_commands_and_schedule_state(client: TestClient, db: FakeDb) -> None:
    spec = {"schedule_cron": "0 * * * *", "enabled": True, "config": {}}
    client.put("/sync/connectors/fake", json=spec)
    started = client.post("/sync/connectors/fake/run").json()
    assert started["workflow_id"].startswith("sync:fake:manual-")
    assert client.post("/sync/connectors/fake/schedule").json() == {"schedule_id": "sync:fake"}
    kinds = [k for k, _ in queued(db)]
    assert kinds == ["start_sync", "apply_schedule"]
    assert queued(db)[1][1] == {"connector": "fake", "cron": "0 * * * *", "enabled": True}
    assert client.get("/sync/connectors").json()[0]["schedule"] is None
    db.rows("sync_connectors")[0]["schedule_state"] = {"paused": False, "runs": 2}
    assert client.get("/sync/connectors").json()[0]["schedule"] == {"paused": False, "runs": 2}


@pytest.mark.anyio
async def test_queued_runs_state_is_empty_without_temporal() -> None:
    assert await QueuedRuns(FakeDb()).state("wf-1") == {}  # type: ignore[arg-type]
