"""Test send and message log on fake database and fake Meta."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from api.auth import AuthUser, current_user
from api.deps import get_db, get_meta
from api.main import app
from meta_client import MetaPermanentError, MetaTransientError
from tests._fakes import FakeDb, FakeMeta

ALLOWED = "+48600000001"
REQUEST = {"template_id": "templates-1", "to_e164": ALLOWED, "body_values": ["Ala"]}


def base_env(monkeypatch: pytest.MonkeyPatch, send_mode: str = "test") -> None:
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.test")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key-for-tests")
    monkeypatch.setenv("PANEL_ALLOWED_EMAIL_DOMAIN", "example.org")
    monkeypatch.setenv("WA_SEND_MODE", send_mode)
    monkeypatch.setenv("WA_ALLOWED_TEST_RECIPIENTS", f"{ALLOWED}, +48600000002")


@pytest.fixture
def db() -> FakeDb:
    db = FakeDb()
    db.rows("templates").append(
        {"id": "templates-1", "name": "welcome_offer", "language": "pl", "status": "APPROVED"}
    )
    return db


@pytest.fixture
def meta() -> FakeMeta:
    return FakeMeta()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, db: FakeDb, meta: FakeMeta) -> Iterator[TestClient]:
    base_env(monkeypatch)
    app.dependency_overrides[current_user] = lambda: AuthUser(id="user-1", email="ala@example.org")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_meta] = lambda: meta
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_test_send_creates_contact_consent_and_message(
    client: TestClient, db: FakeDb, meta: FakeMeta
) -> None:
    response = client.post("/messages/test", json=REQUEST)
    assert response.status_code == 201
    row = response.json()
    assert (row["status"], row["wamid"], row["node_id"], row["run_id"]) == (
        "sent",
        "wamid.T1",
        "test",
        None,
    )
    assert row["idempotency_key"].startswith("test:")
    assert row["meta_response"] == {"messages": [{"id": "wamid.T1"}]}
    assert meta.sent == [(ALLOWED, "welcome_offer", "pl", ["Ala"])]
    assert meta.sent_headers == [None]
    assert [c["phone_e164"] for c in db.rows("contacts")] == [ALLOWED]
    assert [(c["status"], c["source"]) for c in db.rows("consents")] == [
        ("opted_in", "test_allowlist")
    ]
    client.post("/messages/test", json=REQUEST)
    assert len(db.rows("consents")) == 1  # consent is not duplicated on the second send


def test_number_outside_the_allowlist_is_refused_before_anything_is_written(
    client: TestClient, db: FakeDb, meta: FakeMeta
) -> None:
    response = client.post("/messages/test", json={**REQUEST, "to_e164": "+48600000009"})
    assert response.status_code == 403
    assert db.rows("messages") == [] and db.rows("contacts") == [] and meta.sent == []


def test_template_must_be_approved(client: TestClient, db: FakeDb) -> None:
    db.rows("templates")[0]["status"] = "PENDING"
    assert client.post("/messages/test", json=REQUEST).status_code == 409
    assert client.post("/messages/test", json={**REQUEST, "template_id": "nope"}).status_code == 404


def test_meta_errors_mark_the_message_failed(
    client: TestClient, db: FakeDb, meta: FakeMeta
) -> None:
    meta.send_error = MetaPermanentError("Meta 400: (#131026) Message undeliverable", code=131026)
    assert client.post("/messages/test", json=REQUEST).status_code == 422
    meta.send_error = MetaTransientError("Meta 400: (#130429) Rate limit hit", code=130429)
    assert client.post("/messages/test", json=REQUEST).status_code == 503
    failed = db.rows("messages")
    assert [m["status"] for m in failed] == ["failed", "failed"]
    assert failed[0]["error"]["code"] == 131026


def test_bad_phone_format_is_422(client: TestClient) -> None:
    assert (
        client.post("/messages/test", json={**REQUEST, "to_e164": "48600000001"}).status_code == 422
    )


def test_log_lists_messages(client: TestClient, db: FakeDb) -> None:
    client.post("/messages/test", json=REQUEST)
    rows = client.get("/messages").json()
    assert [r["status"] for r in rows] == ["sent"]


def test_live_mode_allows_any_number(
    monkeypatch: pytest.MonkeyPatch, db: FakeDb, meta: FakeMeta
) -> None:
    base_env(monkeypatch, send_mode="live")
    app.dependency_overrides[current_user] = lambda: AuthUser(id="user-1", email="ala@example.org")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_meta] = lambda: meta
    with TestClient(app) as client:
        response = client.post("/messages/test", json={**REQUEST, "to_e164": "+48600000009"})
    app.dependency_overrides.clear()
    assert response.status_code == 201
