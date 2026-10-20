"""Templates API with a fake database and a fake Meta, wired through dependency overrides."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.auth import AuthUser, current_user
from api.deps import get_db, get_meta
from api.main import app
from meta_client import (
    CreatedTemplate,
    MetaError,
    MetaPermanentError,
    MetaTransientError,
    TemplateSpec,
    TemplateState,
)

Row = dict[str, Any]

DRAFT = {
    "name": "welcome_offer",
    "language": "pl",
    "category": "MARKETING",
    "body": "Cześć {{1}}!",
    "example_values": ["Ala"],
}


class FakeDb:
    def __init__(self) -> None:
        self.rows: list[Row] = []

    async def select(self, table: str, **filters: str) -> list[Row]:
        wanted = filters.get("id", "eq.").removeprefix("eq.")
        return [r for r in self.rows if not wanted or r["id"] == wanted]

    async def insert(self, table: str, row: Row) -> Row:
        if any(r["name"] == row["name"] and r["language"] == row["language"] for r in self.rows):
            raise HTTPException(409, "duplicate key value violates unique constraint")
        stored = {"id": f"id-{len(self.rows) + 1}", "meta_template_id": None, **row}
        self.rows.append(stored)
        return stored

    async def update(self, table: str, row_id: str, changes: Row) -> Row:
        for row in self.rows:
            if row["id"] == row_id:
                row.update(changes)
                return row
        raise HTTPException(404, "row not found")


class FakeMeta:
    def __init__(self) -> None:
        self.create_error: MetaError | None = None
        self.state: TemplateState | None = TemplateState(meta_template_id="m-1", status="APPROVED")
        self.created: list[TemplateSpec] = []

    async def create_template(self, spec: TemplateSpec) -> CreatedTemplate:
        if self.create_error is not None:
            raise self.create_error
        self.created.append(spec)
        return CreatedTemplate(meta_template_id="m-1", status="PENDING")

    async def get_template_state(self, name: str, language: str) -> TemplateState | None:
        return self.state


@pytest.fixture
def db() -> FakeDb:
    return FakeDb()


@pytest.fixture
def meta() -> FakeMeta:
    return FakeMeta()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, db: FakeDb, meta: FakeMeta) -> Iterator[TestClient]:
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.test")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key-for-tests")
    monkeypatch.setenv("PANEL_ALLOWED_EMAIL_DOMAIN", "example.org")
    app.dependency_overrides[current_user] = lambda: AuthUser(id="user-1", email="ala@example.org")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_meta] = lambda: meta
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_anonymous_request_is_rejected(client: TestClient) -> None:
    del app.dependency_overrides[current_user]
    assert client.get("/templates").status_code == 401


def test_create_draft_then_list(client: TestClient) -> None:
    created = client.post("/templates", json=DRAFT)
    assert created.status_code == 201
    row = created.json()
    assert row["status"] == "DRAFT" and row["waba_id"] == "local-waba"
    assert row["components"] == {
        "body": "Cześć {{1}}!",
        "example_values": ["Ala"],
        "quick_replies": [],
    }
    assert [r["id"] for r in client.get("/templates").json()] == [row["id"]]


def test_duplicate_draft_is_409_and_bad_spec_is_422(client: TestClient) -> None:
    assert client.post("/templates", json=DRAFT).status_code == 201
    assert client.post("/templates", json=DRAFT).status_code == 409
    assert client.post("/templates", json={**DRAFT, "name": "Bad Name"}).status_code == 422


def test_submit_sends_spec_to_meta_and_stores_pending(client: TestClient, meta: FakeMeta) -> None:
    template_id = client.post("/templates", json=DRAFT).json()["id"]
    submitted = client.post(f"/templates/{template_id}/submit")
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "PENDING"
    assert submitted.json()["meta_template_id"] == "m-1"
    assert meta.created[0].example_values == ["Ala"]
    assert client.post(f"/templates/{template_id}/submit").status_code == 409  # no longer DRAFT


def test_submit_maps_meta_errors(client: TestClient, meta: FakeMeta) -> None:
    template_id = client.post("/templates", json=DRAFT).json()["id"]
    meta.create_error = MetaPermanentError("Meta 400: (#100) Invalid parameter", code=100)
    permanent = client.post(f"/templates/{template_id}/submit")
    assert permanent.status_code == 422 and "Invalid parameter" in permanent.json()["detail"]
    meta.create_error = MetaTransientError("Meta 400: (#130429) Rate limit hit", code=130429)
    assert client.post(f"/templates/{template_id}/submit").status_code == 503
    assert client.get("/templates").json()[0]["status"] == "DRAFT"


def test_sync_stores_meta_verdict(client: TestClient, meta: FakeMeta) -> None:
    template_id = client.post("/templates", json=DRAFT).json()["id"]
    meta.state = TemplateState(
        meta_template_id="m-1", status="REJECTED", rejection_reason="INVALID_FORMAT"
    )
    synced = client.post(f"/templates/{template_id}/sync").json()
    assert (synced["status"], synced["rejection_reason"]) == ("REJECTED", "INVALID_FORMAT")
    meta.state = None
    assert client.post(f"/templates/{template_id}/sync").status_code == 404


def test_unknown_template_is_404(client: TestClient) -> None:
    assert client.post("/templates/nope/submit").status_code == 404


def test_meta_not_configured_is_503(client: TestClient) -> None:
    template_id = client.post("/templates", json=DRAFT).json()["id"]
    del app.dependency_overrides[get_meta]  # real dependency; no META_SYSTEM_USER_TOKEN in env
    response = client.post(f"/templates/{template_id}/submit")
    assert response.status_code == 503 and "not configured" in response.json()["detail"]
