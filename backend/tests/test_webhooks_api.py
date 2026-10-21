"""Meta webhook route: handshake, signature gate, idempotent persistence and run signalling."""

import hashlib
import hmac
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.deps import get_db, get_runs_or_none
from api.main import app
from tests._fakes import FakeDb, FakeTemporal
from worker.workflows.journey import ReplySignal

FIXTURES = Path(__file__).parent / "fixtures" / "meta"
SECRET = "app-secret-for-tests"
VERIFY_TOKEN = "verify-token-for-tests"
HANDSHAKE = {
    "hub.mode": "subscribe",
    "hub.verify_token": VERIFY_TOKEN,
    "hub.challenge": "1158201444",
}


def body(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def signed(raw: bytes) -> dict[str, str]:
    digest = hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return {"X-Hub-Signature-256": f"sha256={digest}", "Content-Type": "application/json"}


def base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.test")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key-for-tests")
    monkeypatch.setenv("PANEL_ALLOWED_EMAIL_DOMAIN", "example.org")


def seed_runs(db: FakeDb) -> None:
    """A contact with two running runs and a finished one; wamid.OUT1 was sent by run r-1."""
    db.rows("contacts").append({"id": "c-1", "phone_e164": "+48600000001"})
    db.rows("journey_runs").extend(
        [
            {"id": "r-1", "workflow_id": "wf-1", "contact_id": "c-1", "status": "running"},
            {"id": "r-2", "workflow_id": "wf-2", "contact_id": "c-1", "status": "running"},
            {"id": "r-3", "workflow_id": "wf-3", "contact_id": "c-1", "status": "completed"},
        ]
    )
    db.rows("messages").append(
        {"id": "m-1", "wamid": "wamid.OUT1", "run_id": "r-1", "status": "sent"}
    )


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
    base_env(monkeypatch)
    monkeypatch.setenv("META_APP_SECRET", SECRET)
    monkeypatch.setenv("META_WEBHOOK_VERIFY_TOKEN", VERIFY_TOKEN)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_runs_or_none] = lambda: temporal
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_handshake_echoes_challenge_only_for_the_right_token(client: TestClient) -> None:
    ok = client.get("/webhooks/meta", params=HANDSHAKE)
    assert (ok.status_code, ok.text) == (200, "1158201444")
    bad = client.get("/webhooks/meta", params={**HANDSHAKE, "hub.verify_token": "nope"})
    assert bad.status_code == 403


def test_post_requires_a_valid_signature(client: TestClient) -> None:
    raw = body("webhook_statuses.json")
    assert client.post("/webhooks/meta", content=raw).status_code == 401
    forged = {**signed(raw), "X-Hub-Signature-256": "sha256=" + "0" * 64}
    assert client.post("/webhooks/meta", content=raw, headers=forged).status_code == 401
    assert client.post("/webhooks/meta", content=raw, headers=signed(raw)).status_code == 200


def test_template_status_updates_the_matching_row(client: TestClient, db: FakeDb) -> None:
    db.rows("templates").append(
        {"id": "t-1", "name": "welcome_offer", "language": "pl", "status": "PENDING"}
    )
    raw = body("webhook_template_status.json")
    response = client.post("/webhooks/meta", content=raw, headers=signed(raw))
    assert response.json() == {"template_status": 2, "message_status": 0, "inbound": 0}
    row = db.rows("templates")[0]
    assert (row["status"], row["meta_template_id"]) == ("APPROVED", "1259544702043867")
    assert row["rejection_reason"] is None
    assert len(db.rows("templates")) == 1  # the en_US verdict had no row to update


def test_message_statuses_are_stored_once_and_update_the_message(
    client: TestClient, db: FakeDb
) -> None:
    db.rows("messages").append({"id": "m-1", "wamid": "wamid.OUT1", "status": "sent"})
    raw = body("webhook_statuses.json")
    client.post("/webhooks/meta", content=raw, headers=signed(raw))
    client.post("/webhooks/meta", content=raw, headers=signed(raw))  # Meta retry
    events = db.rows("message_events")
    assert [(e["wamid"], e["type"], e["message_id"]) for e in events] == [
        ("wamid.OUT1", "delivered", "m-1"),
        ("wamid.OUT2", "failed", None),
    ]
    assert events[1]["occurred_at"] == "2025-06-18T16:23:00+00:00"
    assert db.rows("messages")[0]["status"] == "delivered"


def test_inbound_creates_contact_once_and_stop_opts_out(client: TestClient, db: FakeDb) -> None:
    raw = body("webhook_inbound.json")
    client.post("/webhooks/meta", content=raw, headers=signed(raw))
    client.post("/webhooks/meta", content=raw, headers=signed(raw))  # Meta retry
    contacts = db.rows("contacts")
    assert [c["phone_e164"] for c in contacts] == ["+48600000001"]
    inbound = db.rows("inbound_messages")
    assert [(m["wamid"], m["text"], m["button_payload"], m["context_wamid"]) for m in inbound] == [
        ("wamid.IN1", "STOP", None, None),
        ("wamid.IN2", None, "YES", "wamid.OUT1"),
    ]
    consents = [(c["contact_id"], c["status"]) for c in db.rows("consents")]
    assert consents == [(contacts[0]["id"], "opted_out")]


def test_unconfigured_webhook_answers_503(monkeypatch: pytest.MonkeyPatch) -> None:
    base_env(monkeypatch)
    monkeypatch.delenv("META_APP_SECRET", raising=False)
    with TestClient(app) as client:
        assert client.get("/webhooks/meta", params=HANDSHAKE).status_code == 503


def test_inbound_signals_the_right_runs_once(
    client: TestClient, db: FakeDb, temporal: FakeTemporal
) -> None:
    seed_runs(db)
    raw = body("webhook_inbound.json")
    client.post("/webhooks/meta", content=raw, headers=signed(raw))
    client.post("/webhooks/meta", content=raw, headers=signed(raw))  # Meta retry: no new signals
    stop = ReplySignal(wamid="wamid.IN1", text="STOP")
    yes = ReplySignal(wamid="wamid.IN2", button_payload="YES", context_wamid="wamid.OUT1")
    assert temporal.signals == [
        ("wf-1", "inbound_message", stop),  # no context: every running run of the contact
        ("wf-2", "inbound_message", stop),
        ("wf-1", "opt_out", None),  # STOP: every running run, the completed wf-3 is left alone
        ("wf-2", "opt_out", None),
        ("wf-1", "inbound_message", yes),  # context wamid.OUT1: only the run that sent it
    ]


def test_status_signals_the_message_run_and_temporal_outage_still_persists(
    client: TestClient, db: FakeDb, temporal: FakeTemporal
) -> None:
    seed_runs(db)
    raw = body("webhook_statuses.json")
    client.post("/webhooks/meta", content=raw, headers=signed(raw))
    assert [(s[0], s[1]) for s in temporal.signals] == [("wf-1", "message_status")]
    payload = temporal.signals[0][2]
    assert isinstance(payload, dict)
    assert (payload["wamid"], payload["status"]) == ("wamid.OUT1", "delivered")

    app.dependency_overrides[get_runs_or_none] = lambda: None  # Temporal is down
    raw = body("webhook_inbound.json")
    assert client.post("/webhooks/meta", content=raw, headers=signed(raw)).status_code == 200
    assert [m["wamid"] for m in db.rows("inbound_messages")] == ["wamid.IN1", "wamid.IN2"]
    assert [c["status"] for c in db.rows("consents")] == ["opted_out"]
    assert len(temporal.signals) == 1  # nothing new, the inbound was only stored


def test_temporal_connect_failure_is_an_outage_not_an_error(
    monkeypatch: pytest.MonkeyPatch, db: FakeDb
) -> None:
    """The SDK raises RuntimeError when it cannot connect; the webhook must still answer 200."""
    base_env(monkeypatch)
    monkeypatch.setenv("META_APP_SECRET", SECRET)
    monkeypatch.setenv("META_WEBHOOK_VERIFY_TOKEN", VERIFY_TOKEN)

    async def failing_connect(settings: object) -> None:
        raise RuntimeError("Failed client connect: Server connection error")

    monkeypatch.setattr("api.deps.connect", failing_connect)
    app.dependency_overrides[get_db] = lambda: db  # get_runs_or_none runs for real
    with TestClient(app) as client:
        raw = body("webhook_inbound.json")
        assert client.post("/webhooks/meta", content=raw, headers=signed(raw)).status_code == 200
    app.dependency_overrides.clear()
    assert [m["wamid"] for m in db.rows("inbound_messages")] == ["wamid.IN1", "wamid.IN2"]
