"""Journeys API on fake storage and fake Temporal; the definition is the guide's section 4.1 one."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.auth import AuthUser, current_user
from api.deps import get_db, get_runs
from api.main import app
from tests._fakes import FakeDb, FakeTemporal


@pytest.fixture
def db() -> FakeDb:
    db = FakeDb()
    db.rows("templates").append(
        {"id": "tpl-1", "name": "welcome_offer", "language": "pl", "status": "APPROVED"}
    )
    for contact_id in ("c-1", "c-2"):
        db.rows("contacts").append({"id": contact_id, "phone_e164": f"+4860000000{contact_id[-1]}"})
    return db


@pytest.fixture
def temporal() -> FakeTemporal:
    return FakeTemporal()


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch, db: FakeDb, temporal: FakeTemporal
) -> Iterator[TestClient]:
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.test")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key-for-tests")
    monkeypatch.setenv("PANEL_ALLOWED_EMAIL_DOMAIN", "example.org")
    app.dependency_overrides[current_user] = lambda: AuthUser(id="user-1", email="ala@example.org")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_runs] = lambda: temporal
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def published(client: TestClient, definition: dict[str, Any]) -> str:
    journey_id: str = client.post("/journeys", json={"name": "welcome"}).json()["id"]
    assert client.post(f"/journeys/{journey_id}/versions", json=definition).status_code == 201
    return journey_id


def test_create_and_list_journeys(client: TestClient) -> None:
    created = client.post("/journeys", json={"name": "welcome"})
    assert created.status_code == 201 and created.json()["status"] == "draft"
    assert [j["name"] for j in client.get("/journeys").json()] == ["welcome"]


def test_publish_validates_schema_and_graph(
    client: TestClient, db: FakeDb, guide_example_json: dict[str, Any]
) -> None:
    journey_id = client.post("/journeys", json={"name": "welcome"}).json()["id"]
    bad_schema = client.post(f"/journeys/{journey_id}/versions", json={"schema_version": 2})
    assert bad_schema.status_code == 422 and "schema_version" in bad_schema.json()["detail"][0]
    db.rows("templates")[0]["status"] = "PENDING"
    bad_graph = client.post(f"/journeys/{journey_id}/versions", json=guide_example_json)
    assert bad_graph.status_code == 422 and "not APPROVED" in bad_graph.json()["detail"][0]
    db.rows("templates")[0]["status"] = "APPROVED"
    first = client.post(f"/journeys/{journey_id}/versions", json=guide_example_json).json()
    second = client.post(f"/journeys/{journey_id}/versions", json=guide_example_json).json()
    assert (first["version"], second["version"]) == (1, 2)
    assert first["definition"] == guide_example_json
    assert db.rows("journeys")[0]["status"] == "active"


def test_start_runs_once_per_contact(
    client: TestClient, db: FakeDb, temporal: FakeTemporal, guide_example_json: dict[str, Any]
) -> None:
    journey_id = published(client, guide_example_json)
    first = client.post(f"/journeys/{journey_id}/runs", json={"contact_ids": ["c-1", "c-2"]})
    assert first.status_code == 201
    assert len(first.json()["started"]) == 2 and first.json()["skipped"] == []
    workflow_ids = [workflow_id for workflow_id, _ in temporal.started]
    assert workflow_ids == [
        f"journey:{journey_id}:contact:c-1",
        f"journey:{journey_id}:contact:c-2",
    ]
    run_input = temporal.started[0][1]
    assert (run_input.contact_id, run_input.definition) == ("c-1", guide_example_json)
    again = client.post(f"/journeys/{journey_id}/runs", json={"contact_ids": ["c-1"]}).json()
    assert again == {"started": [], "skipped": ["c-1"]}  # still running in the database
    assert len(db.rows("journey_runs")) == 2


def test_temporal_refusal_marks_the_row_cancelled(
    client: TestClient, db: FakeDb, temporal: FakeTemporal, guide_example_json: dict[str, Any]
) -> None:
    journey_id = published(client, guide_example_json)
    temporal.active.add(f"journey:{journey_id}:contact:c-1")  # a run Temporal still knows about
    result = client.post(f"/journeys/{journey_id}/runs", json={"contact_ids": ["c-1"]}).json()
    assert result == {"started": [], "skipped": ["c-1"]}
    assert db.rows("journey_runs")[0]["status"] == "cancelled"


def test_start_needs_a_published_version(client: TestClient) -> None:
    journey_id = client.post("/journeys", json={"name": "draft only"}).json()["id"]
    assert (
        client.post(f"/journeys/{journey_id}/runs", json={"contact_ids": ["c-1"]}).status_code
        == 409
    )
    assert client.post("/journeys/nope/runs", json={"contact_ids": ["c-1"]}).status_code == 404


def test_list_get_and_cancel_runs(
    client: TestClient, db: FakeDb, temporal: FakeTemporal, guide_example_json: dict[str, Any]
) -> None:
    journey_id = published(client, guide_example_json)
    run_id = client.post(f"/journeys/{journey_id}/runs", json={"contact_ids": ["c-1"]}).json()[
        "started"
    ][0]
    runs = client.get(f"/journeys/{journey_id}/runs").json()
    assert [r["status"] for r in runs] == ["running"]
    live = client.get(f"/runs/{run_id}").json()
    assert live["live"] == {"node_id": "n2", "waiting": "sleep"}
    cancelled = client.post(f"/runs/{run_id}/cancel")
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    assert temporal.cancelled == [f"journey:{journey_id}:contact:c-1"]
    assert client.post(f"/runs/{run_id}/cancel").status_code == 409
    assert "live" not in client.get(f"/runs/{run_id}").json()
