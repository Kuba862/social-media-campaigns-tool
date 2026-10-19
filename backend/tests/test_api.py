"""API smoke tests: /healthz is open, /me needs a valid token from an allowed domain."""

from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.test")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key-for-tests")
    monkeypatch.setenv("PANEL_ALLOWED_EMAIL_DOMAIN", "example.org")
    with TestClient(app) as client:  # `with` runs the lifespan
        yield client


def fake_supabase(email: str | None) -> httpx.AsyncClient:
    """Stands in for Supabase Auth: the only valid token is 'good-token'."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/auth/v1/user"
        if request.headers.get("Authorization") != "Bearer good-token":
            return httpx.Response(401, json={"msg": "invalid token"})
        return httpx.Response(200, json={"id": "user-1", "email": email})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_healthz_is_open(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}


def test_missing_token_is_401(client: TestClient) -> None:
    assert client.get("/me").status_code == 401


def test_invalid_token_is_401(client: TestClient) -> None:
    app.state.http = fake_supabase("ala@example.org")
    response = client.get("/me", headers={"Authorization": "Bearer bad-token"})
    assert response.status_code == 401


def test_other_domain_is_403(client: TestClient) -> None:
    app.state.http = fake_supabase("ala@evil.com")
    response = client.get("/me", headers={"Authorization": "Bearer good-token"})
    assert response.status_code == 403


def test_allowed_user_gets_through(client: TestClient) -> None:
    app.state.http = fake_supabase("Ala@Example.org")
    response = client.get("/me", headers={"Authorization": "Bearer good-token"})
    assert response.status_code == 200
    assert response.json() == {"id": "user-1", "email": "ala@example.org"}
