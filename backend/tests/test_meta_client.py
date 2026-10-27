"""meta_client against a fake Meta: fixtures written from the Cloud API docs, no network."""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from meta_client import MetaClient, MetaPermanentError, MetaTransientError, TemplateSpec
from meta_client.mapping import message_payload, template_create_payload, text_message_payload

FIXTURES = Path(__file__).parent / "fixtures" / "meta"


def fixture(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / name).read_text())
    return data


class FakeMeta:
    """Records the last request and answers with a canned response."""

    def __init__(self, status: int = 200, body: dict[str, Any] | None = None) -> None:
        self.status = status
        self.body = body or {}
        self.last: httpx.Request | None = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.last = request
        return httpx.Response(self.status, json=self.body)

    def client(self) -> MetaClient:
        http = httpx.AsyncClient(transport=httpx.MockTransport(self.handler))
        return MetaClient(
            http,
            graph_version="v24.0",
            waba_id="WABA1",
            phone_number_id="PHONE1",
            access_token="test-token",
        )

    def sent_json(self) -> dict[str, Any]:
        assert self.last is not None
        body: dict[str, Any] = json.loads(self.last.content)
        return body


SPEC = TemplateSpec(
    name="welcome_offer",
    language="pl",
    category="MARKETING",
    body="Cześć {{1}}! Twoja oferta: {{2}}.",
    example_values=["Ala", "20%"],
    quick_replies=["Tak", "Nie"],
)


def test_template_payload_has_positional_examples_and_buttons() -> None:
    payload = template_create_payload(SPEC)
    assert payload["name"] == "welcome_offer"
    assert payload["parameter_format"] == "positional"
    body, buttons = payload["components"]
    assert body == {"type": "BODY", "text": SPEC.body, "example": {"body_text": [["Ala", "20%"]]}}
    assert [b["text"] for b in buttons["buttons"]] == ["Tak", "Nie"]


def test_example_values_must_match_placeholders() -> None:
    with pytest.raises(ValueError, match="2 placeholders but 1"):
        TemplateSpec(
            name="x", language="pl", category="UTILITY", body="Hi {{1}} {{2}}", example_values=["a"]
        )


def test_message_payload_strips_plus_and_omits_empty_components() -> None:
    with_values = message_payload("+48600000001", "welcome_offer", "pl", ["Ala"])
    assert with_values["to"] == "48600000001"
    parameters = with_values["template"]["components"][0]["parameters"]
    assert parameters == [{"type": "text", "text": "Ala"}]
    assert "components" not in message_payload("48600000001", "welcome_offer", "pl", [])["template"]


@pytest.mark.anyio
async def test_create_template_posts_to_waba_and_returns_id() -> None:
    meta = FakeMeta(body=fixture("template_create.json"))
    created = await meta.client().create_template(SPEC)
    assert meta.last is not None
    assert meta.last.method == "POST"
    assert meta.last.url.path == "/v24.0/WABA1/message_templates"
    assert meta.last.headers["Authorization"] == "Bearer test-token"
    assert meta.sent_json()["category"] == "MARKETING"
    assert (created.meta_template_id, created.status) == ("1259544702043867", "PENDING")


@pytest.mark.anyio
async def test_template_state_picks_language_and_maps_rejection() -> None:
    meta = FakeMeta(body=fixture("template_list.json"))
    client = meta.client()
    rejected = await client.get_template_state("welcome_offer", "pl")
    approved = await client.get_template_state("welcome_offer", "en_US")
    missing = await client.get_template_state("welcome_offer", "de")
    assert rejected is not None and rejected.status == "REJECTED"
    assert rejected.rejection_reason == "INVALID_FORMAT"
    assert approved is not None and approved.status == "APPROVED"
    assert approved.rejection_reason is None  # Meta says "NONE", we say nothing
    assert missing is None


@pytest.mark.anyio
async def test_send_template_posts_to_phone_number_and_returns_wamid() -> None:
    meta = FakeMeta(body=fixture("message_send.json"))
    result = await meta.client().send_template("+48600000001", "welcome_offer", "pl", ["Ala"])
    assert meta.last is not None and meta.last.url.path == "/v24.0/PHONE1/messages"
    assert meta.sent_json()["messaging_product"] == "whatsapp"
    assert result.wamid.startswith("wamid.") and result.status == "accepted"


@pytest.mark.anyio
async def test_throttling_is_transient_even_as_http_400() -> None:
    meta = FakeMeta(status=400, body=fixture("error_throttled.json"))
    with pytest.raises(MetaTransientError) as info:
        await meta.client().send_template("+48600000001", "welcome_offer", "pl", [])
    assert info.value.code == 130429 and info.value.http_status == 400


@pytest.mark.anyio
async def test_server_error_is_transient() -> None:
    meta = FakeMeta(status=503, body={})
    with pytest.raises(MetaTransientError):
        await meta.client().create_template(SPEC)


@pytest.mark.anyio
async def test_network_error_is_transient() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    http = httpx.AsyncClient(transport=httpx.MockTransport(boom))
    client = MetaClient(
        http, graph_version="v24.0", waba_id="W", phone_number_id="P", access_token="t"
    )
    with pytest.raises(MetaTransientError):
        await client.create_template(SPEC)


@pytest.mark.anyio
async def test_validation_error_is_permanent_with_code() -> None:
    meta = FakeMeta(status=400, body=fixture("error_invalid_parameter.json"))
    with pytest.raises(MetaPermanentError) as info:
        await meta.client().send_template("+48600000001", "nope", "pl", [])
    assert (info.value.code, info.value.subcode) == (100, 2494010)
    assert "Invalid parameter" in str(info.value)


def test_text_payload_is_a_plain_message_without_link_preview() -> None:
    payload = text_message_payload("+48600000001", "Cześć Ala")
    assert (payload["type"], payload["to"]) == ("text", "48600000001")
    assert payload["text"] == {"preview_url": False, "body": "Cześć Ala"}


@pytest.mark.anyio
async def test_send_text_posts_to_phone_number_and_returns_wamid() -> None:
    meta = FakeMeta(body=fixture("message_send.json"))
    result = await meta.client().send_text("+48600000001", "Cześć Ala")
    assert meta.last is not None and meta.last.url.path == "/v24.0/PHONE1/messages"
    assert meta.sent_json()["type"] == "text"
    assert result.wamid.startswith("wamid.")
