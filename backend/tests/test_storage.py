"""PostgrestClient against a fake PostgREST: request shape, response parsing, error classes."""

import json
from typing import Any

import httpx
import pytest

from storage.postgrest import (
    ConflictError,
    NotFoundError,
    PostgrestClient,
    StorageRequestError,
    StorageUnavailable,
)


class FakePostgrest:
    def __init__(self, status: int = 200, body: Any = None) -> None:
        self.status = status
        self.body = [] if body is None else body
        self.last: httpx.Request | None = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.last = request
        return httpx.Response(self.status, json=self.body)

    def client(self) -> PostgrestClient:
        http = httpx.AsyncClient(transport=httpx.MockTransport(self.handler))
        return PostgrestClient(http, supabase_url="http://supabase.test/", service_role_key="srk")

    def request(self) -> httpx.Request:
        assert self.last is not None
        return self.last


@pytest.mark.anyio
async def test_select_sends_filters_columns_and_service_role_headers() -> None:
    fake = FakePostgrest(body=[{"id": "t-1"}])
    rows = await fake.client().select("templates", columns="*,contacts(phone_e164)", id="eq.t-1")
    request = fake.request()
    assert rows == [{"id": "t-1"}]
    assert request.method == "GET" and request.url.path == "/rest/v1/templates"
    assert dict(request.url.params) == {
        "select": "*,contacts(phone_e164)",
        "order": "created_at.desc",
        "id": "eq.t-1",
    }
    assert request.headers["apikey"] == "srk"
    assert request.headers["Authorization"] == "Bearer srk"
    assert request.headers["Prefer"] == "return=representation"


@pytest.mark.anyio
async def test_insert_ignore_and_upsert_set_conflict_resolution() -> None:
    fake = FakePostgrest(body=[])
    skipped = await fake.client().insert_ignore(
        "messages", {"wamid": "w"}, on_conflict="wamid,type"
    )
    assert skipped is None
    assert dict(fake.request().url.params) == {"on_conflict": "wamid,type"}
    assert fake.request().headers["Prefer"] == "resolution=ignore-duplicates,return=representation"
    assert json.loads(fake.request().content) == {"wamid": "w"}

    fake = FakePostgrest(body=[{"id": "c-1", "phone_e164": "+48600000001"}])
    stored = await fake.client().upsert("contacts", {"phone_e164": "+48600000001"}, "phone_e164")
    assert stored["id"] == "c-1"
    assert fake.request().headers["Prefer"] == "resolution=merge-duplicates,return=representation"


@pytest.mark.anyio
async def test_update_patches_by_id_and_reports_missing_rows() -> None:
    fake = FakePostgrest(body=[{"id": "t-1", "status": "APPROVED"}])
    row = await fake.client().update("templates", "t-1", {"status": "APPROVED"})
    assert row["status"] == "APPROVED"
    assert fake.request().method == "PATCH"
    assert dict(fake.request().url.params) == {"id": "eq.t-1"}

    with pytest.raises(NotFoundError, match="templates row not found"):
        await FakePostgrest(body=[]).client().update("templates", "nope", {"status": "X"})


@pytest.mark.anyio
async def test_errors_map_to_classes_and_transience() -> None:
    conflict = FakePostgrest(409, {"message": "duplicate key value violates unique constraint"})
    with pytest.raises(ConflictError, match="duplicate key") as info:
        await conflict.client().insert("templates", {"name": "x"})
    assert not info.value.transient

    with pytest.raises(StorageRequestError) as bad:
        await FakePostgrest(400, {"message": "invalid input"}).client().insert("t", {})
    assert (bad.value.status, bad.value.transient) == (400, False)

    with pytest.raises(StorageRequestError) as down:
        await FakePostgrest(502, {"message": "upstream"}).client().insert("t", {})
    assert down.value.transient

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    http = httpx.AsyncClient(transport=httpx.MockTransport(boom))
    client = PostgrestClient(http, supabase_url="http://supabase.test", service_role_key="srk")
    with pytest.raises(StorageUnavailable) as gone:
        await client.select("templates")
    assert gone.value.transient


@pytest.mark.anyio
async def test_delete_filters_by_id_and_reports_a_missing_row() -> None:
    fake = FakePostgrest(body=[{"id": "t-1"}])
    await fake.client().delete("templates", "t-1")
    request = fake.request()
    assert request.method == "DELETE" and dict(request.url.params) == {"id": "eq.t-1"}
    with pytest.raises(NotFoundError):
        await FakePostgrest(body=[]).client().delete("templates", "t-2")
