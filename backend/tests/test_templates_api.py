"""Templates API with a fake database and a fake Meta, wired through dependency overrides."""

from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from api.auth import AuthUser, current_user
from api.deps import get_db, get_http, get_meta, get_meta_or_none
from api.main import app
from meta_client import (
    MetaPermanentError,
    MetaTransientError,
    TemplateState,
)
from tests._fakes import FakeDb, FakeMeta

Row = dict[str, Any]

DRAFT = {
    "name": "welcome_offer",
    "language": "pl",
    "category": "MARKETING",
    "body": "Cześć {{1}}!",
    "example_values": ["Ala"],
}


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
        "header": None,
        "header_image_url": None,
        "body": "Cześć {{1}}!",
        "footer": None,
        "example_values": ["Ala"],
        "buttons": [],
        "variables": ["1"],
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


def test_delete_draft_needs_no_meta_and_removes_the_row(client: TestClient, db: FakeDb) -> None:
    template_id = client.post("/templates", json=DRAFT).json()["id"]
    assert client.delete(f"/templates/{template_id}").status_code == 204
    assert db.rows("templates") == []
    assert client.delete(f"/templates/{template_id}").status_code == 404


def test_delete_submitted_template_deletes_it_at_meta_first(
    client: TestClient, db: FakeDb, meta: FakeMeta
) -> None:
    template_id = client.post("/templates", json=DRAFT).json()["id"]
    client.post(f"/templates/{template_id}/submit")
    unconfigured = client.delete(f"/templates/{template_id}")
    assert unconfigured.status_code == 503  # Meta knows the template, so Meta must be reachable
    app.dependency_overrides[get_meta_or_none] = lambda: meta
    assert client.delete(f"/templates/{template_id}").status_code == 204
    assert meta.deleted == [("welcome_offer", "m-1")] and db.rows("templates") == []


V2 = {
    "name": "oferta_1",
    "language": "pl",
    "category": "UTILITY",
    "header": "Nowa oferta",
    "body": "Cześć {{first_name}}, Twoja oferta: {{offer}}.",
    "footer": "Odpowiedz STOP, aby zrezygnować",
    "buttons": [
        {"type": "quick_reply", "text": "Tak"},
        {"type": "url", "text": "Zobacz", "url": "https://example.org/oferta"},
    ],
    "example_values": ["Ala", "20%"],
}


def test_create_v2_draft_stores_parts_and_variable_names(client: TestClient) -> None:
    row = client.post("/templates", json=V2).json()
    components = row["components"]
    assert components["variables"] == ["first_name", "offer"]
    assert [b["type"] for b in components["buttons"]] == ["quick_reply", "url"]
    assert (components["header"], components["footer"]) == (V2["header"], V2["footer"])
    bad = client.post(
        "/templates",
        json={**V2, "name": "zle", "body": "{{first_name}} cześć", "example_values": ["Ala"]},
    )
    assert bad.status_code == 422 and "start with a variable" in bad.text


def test_legacy_quick_replies_become_buttons_and_old_rows_still_submit(
    client: TestClient, db: FakeDb, meta: FakeMeta
) -> None:
    row = client.post("/templates", json={**DRAFT, "quick_replies": ["Tak", "Nie"]}).json()
    assert [b["text"] for b in row["components"]["buttons"]] == ["Tak", "Nie"]
    db.rows("templates").append(  # a row written before 11c
        {
            "id": "old-1",
            "name": "stary",
            "language": "pl",
            "category": "MARKETING",
            "status": "DRAFT",
            "components": {
                "body": "Hej {{1}}!",
                "example_values": ["Ala"],
                "quick_replies": ["Ok"],
            },
        }
    )
    assert client.post("/templates/old-1/submit").status_code == 200
    assert [b.text for b in meta.created[-1].all_buttons] == ["Ok"]


IMAGE_DRAFT = {
    "name": "promo_1",
    "language": "pl",
    "category": "MARKETING",
    "header_image_url": "https://cdn.example.org/promo.png",
    "body": "Cześć {{first_name}}, zobacz naszą akcję.",
    "example_values": ["Ala"],
}


def fake_http(status: int, content_type: str, body: bytes) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == IMAGE_DRAFT["header_image_url"]
        return httpx.Response(status, content=body, headers={"content-type": content_type})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_submit_uploads_the_header_image_sample_first(client: TestClient, meta: FakeMeta) -> None:
    template_id = client.post("/templates", json=IMAGE_DRAFT).json()["id"]
    app.dependency_overrides[get_http] = lambda: fake_http(200, "image/png", b"PNGDATA")
    assert client.post(f"/templates/{template_id}/submit").status_code == 200
    assert meta.uploads == [("image/png", 7)] and meta.created_handles == ["4::sample-handle"]


def test_submit_refuses_a_header_image_that_is_not_a_small_jpeg_or_png(
    client: TestClient, meta: FakeMeta
) -> None:
    template_id = client.post("/templates", json=IMAGE_DRAFT).json()["id"]
    app.dependency_overrides[get_http] = lambda: fake_http(200, "text/html", b"<html>")
    html = client.post(f"/templates/{template_id}/submit")
    assert html.status_code == 422 and "JPEG or PNG" in html.json()["detail"]
    app.dependency_overrides[get_http] = lambda: fake_http(
        200, "image/jpeg", b"x" * (5 * 1024 * 1024 + 1)
    )
    big = client.post(f"/templates/{template_id}/submit")
    assert big.status_code == 422 and "5 MB" in big.json()["detail"]
    assert meta.uploads == [] and client.get("/templates").json()[0]["status"] == "DRAFT"


SERVICE = {"name": "podziekowanie", "language": "pl", "body": "Dziękujemy za odpowiedź!"}


def test_service_message_is_ready_at_once_and_never_goes_to_meta(client: TestClient) -> None:
    row = client.post(
        "/templates/service", json={**SERVICE, "image_url": "https://x.y/a.png"}
    ).json()
    assert (row["kind"], row["status"], row["category"]) == ("service", "READY", "SERVICE")
    assert row["components"] == {
        "body": SERVICE["body"],
        "image_url": "https://x.y/a.png",
        "variables": [],
    }
    assert client.post(f"/templates/{row['id']}/submit").status_code == 409
    assert client.post(f"/templates/{row['id']}/sync").status_code == 409
    bad = client.post("/templates/service", json={**SERVICE, "body": "Hej {{first_name}}"})
    assert bad.status_code == 422
    assert client.delete(f"/templates/{row['id']}").status_code == 204
