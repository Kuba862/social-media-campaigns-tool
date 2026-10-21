"""Sync API on fake storage and fake Temporal."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from api.auth import AuthUser, current_user
from api.deps import get_db, get_runs, get_runs_or_none
from api.main import app
from tests._fakes import FakeDb, FakeTemporal

FAKE = {"schedule_cron": "0 * * * *", "enabled": True, "config": {"default_region": "PL"}}


@pytest.fixture
def db() -> FakeDb:
    return FakeDb()


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
    app.dependency_overrides[get_runs_or_none] = lambda: temporal
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_register_checks_the_name_and_cron_and_upserts_by_name(
    client: TestClient, db: FakeDb
) -> None:
    first = client.put("/sync/connectors/fake", json=FAKE)
    assert first.status_code == 200 and first.json()["enabled"] is True
    second = client.put("/sync/connectors/fake", json={**FAKE, "enabled": False})
    assert second.json()["id"] == first.json()["id"] and second.json()["enabled"] is False
    assert len(db.rows("sync_connectors")) == 1
    unknown = client.put("/sync/connectors/nope", json=FAKE)
    assert unknown.status_code == 422 and "known: fake, postgres" in unknown.json()["detail"]
    assert (
        client.put("/sync/connectors/fake", json={**FAKE, "schedule_cron": "hourly"}).status_code
        == 422
    )


def test_run_now_and_schedule_go_through_temporal(
    client: TestClient, temporal: FakeTemporal
) -> None:
    client.put("/sync/connectors/fake", json=FAKE)
    started = client.post("/sync/connectors/fake/run")
    assert started.status_code == 202 and started.json() == {"workflow_id": "sync:fake:manual-1"}
    assert temporal.sync_started == ["sync:fake:manual-1"]
    scheduled = client.post("/sync/connectors/fake/schedule")
    assert scheduled.status_code == 200
    assert (scheduled.json()["schedule_id"], scheduled.json()["paused"]) == ("sync:fake", False)
    assert temporal.schedules == {"fake": ("0 * * * *", True)}
    listed = client.get("/sync/connectors").json()
    assert [(c["name"], c["schedule"]["cron"]) for c in listed] == [("fake", ["0 * * * *"])]
    assert client.post("/sync/connectors/postgres/run").status_code == 404  # not registered


def test_runs_list_filters_by_connector(client: TestClient, db: FakeDb) -> None:
    fake = client.put("/sync/connectors/fake", json=FAKE).json()
    pg = client.put("/sync/connectors/postgres", json={**FAKE, "config": {}}).json()
    db.rows("sync_runs").extend(
        [
            {
                "id": "sr-1",
                "connector_id": fake["id"],
                "status": "succeeded",
                "stats": {"extracted": 4},
            },
            {"id": "sr-2", "connector_id": pg["id"], "status": "failed", "stats": {}},
        ]
    )
    assert [r["id"] for r in client.get("/sync/runs").json()] == ["sr-1", "sr-2"]
    assert [r["id"] for r in client.get("/sync/runs", params={"connector": "fake"}).json()] == [
        "sr-1"
    ]
    assert client.get("/sync/runs", params={"connector": "nope"}).status_code == 404
