"""Webhook parsing and signature check on fixtures written from the Cloud API docs."""

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

from meta_client import (
    InboundMessageEvent,
    MessageStatusEvent,
    TemplateStatusEvent,
    parse_webhook,
    signature_is_valid,
)

FIXTURES = Path(__file__).parent / "fixtures" / "meta"
SECRET = "app-secret-for-tests"


def fixture(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / name).read_text())
    return data


def sign(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_signature_accepts_the_documented_scheme_only() -> None:
    body = b'{"object":"whatsapp_business_account"}'
    assert signature_is_valid(SECRET, body, sign(body))
    assert not signature_is_valid(SECRET, body, sign(body, "other-secret"))
    assert not signature_is_valid(SECRET, body + b" ", sign(body))
    assert not signature_is_valid(SECRET, body, None)
    assert not signature_is_valid(SECRET, body, sign(body).removeprefix("sha256="))


def test_template_status_events_map_reason_and_id() -> None:
    approved, rejected = parse_webhook(fixture("webhook_template_status.json"))
    assert isinstance(approved, TemplateStatusEvent) and isinstance(rejected, TemplateStatusEvent)
    assert (approved.name, approved.language) == ("welcome_offer", "pl")
    assert approved.status == "APPROVED"
    assert approved.meta_template_id == "1259544702043867"
    assert approved.rejection_reason is None
    assert (rejected.status, rejected.rejection_reason) == ("REJECTED", "INVALID_FORMAT")


def test_message_statuses_keep_errors_and_skip_unknown_status() -> None:
    delivered, failed = parse_webhook(fixture("webhook_statuses.json"))
    assert isinstance(delivered, MessageStatusEvent) and isinstance(failed, MessageStatusEvent)
    assert (delivered.wamid, delivered.status, delivered.occurred_at) == (
        "wamid.OUT1",
        "delivered",
        1750263773,
    )
    assert delivered.recipient_phone == "+48600000001"
    assert delivered.error is None
    assert failed.status == "failed" and failed.error is not None
    assert failed.error["code"] == 131026


def test_inbound_text_and_button_reply() -> None:
    text, button = parse_webhook(fixture("webhook_inbound.json"))
    assert isinstance(text, InboundMessageEvent) and isinstance(button, InboundMessageEvent)
    assert (text.from_phone, text.type, text.text) == ("+48600000001", "text", "STOP")
    assert text.button_payload is None and text.context_wamid is None
    assert (button.type, button.button_payload, button.context_wamid) == (
        "button",
        "YES",
        "wamid.OUT1",
    )
    assert button.text is None


def test_unknown_fields_and_empty_payloads_are_ignored() -> None:
    assert parse_webhook({}) == []
    payload = {"entry": [{"changes": [{"field": "account_update", "value": {"x": 1}}]}]}
    assert parse_webhook(payload) == []
