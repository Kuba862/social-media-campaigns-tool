"""Webhook side of the Meta boundary: signature check and parsing of the three change kinds."""

import hashlib
import hmac
from typing import Any, Literal, get_args

from meta_client.models import Frozen, TemplateStatus

MessageStatus = Literal["sent", "delivered", "read", "failed"]

KNOWN_TEMPLATE_STATUSES = frozenset(get_args(TemplateStatus))
KNOWN_MESSAGE_STATUSES = frozenset(get_args(MessageStatus))


def signature_is_valid(app_secret: str, raw_body: bytes, header: str | None) -> bool:
    """Checks X-Hub-Signature-256: "sha256=" + HMAC-SHA256(app secret, raw body), constant time."""
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


class TemplateStatusEvent(Frozen):
    kind: Literal["template_status"] = "template_status"
    meta_template_id: str
    name: str
    language: str
    status: TemplateStatus
    rejection_reason: str | None


class MessageStatusEvent(Frozen):
    kind: Literal["message_status"] = "message_status"
    wamid: str
    status: MessageStatus
    recipient_phone: str
    occurred_at: int  # unix seconds, as Meta sends it
    error: dict[str, Any] | None


class InboundMessageEvent(Frozen):
    kind: Literal["inbound"] = "inbound"
    wamid: str
    from_phone: str
    type: str
    text: str | None
    button_payload: str | None
    context_wamid: str | None  # the wamid of our message this one replies to
    received_at: int


WebhookEvent = TemplateStatusEvent | MessageStatusEvent | InboundMessageEvent


def parse_webhook(payload: dict[str, Any]) -> list[WebhookEvent]:
    """Flattens entry[].changes[] into typed events. Unknown fields and statuses are skipped."""
    events: list[WebhookEvent] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            field, value = change.get("field"), change.get("value", {})
            if field == "message_template_status_update":
                if value.get("event") in KNOWN_TEMPLATE_STATUSES:
                    events.append(_template_status(value))
            elif field == "messages":
                for status in value.get("statuses", []):
                    if status.get("status") in KNOWN_MESSAGE_STATUSES:
                        events.append(_message_status(status))
                events.extend(_inbound(message) for message in value.get("messages", []))
    return events


def _e164(digits: str) -> str:
    return "+" + digits.lstrip("+")


def _template_status(value: dict[str, Any]) -> TemplateStatusEvent:
    reason = value.get("reason")
    return TemplateStatusEvent(
        meta_template_id=str(value["message_template_id"]),
        name=value["message_template_name"],
        language=value["message_template_language"],
        status=value["event"],
        rejection_reason=None if reason in (None, "NONE") else str(reason),
    )


def _message_status(status: dict[str, Any]) -> MessageStatusEvent:
    errors = status.get("errors") or []
    return MessageStatusEvent(
        wamid=status["id"],
        status=status["status"],
        recipient_phone=_e164(status.get("recipient_id", "")),
        occurred_at=int(status["timestamp"]),
        error=errors[0] if errors else None,
    )


def _inbound(message: dict[str, Any]) -> InboundMessageEvent:
    return InboundMessageEvent(
        wamid=message["id"],
        from_phone=_e164(message["from"]),
        type=message.get("type", "unknown"),
        text=message.get("text", {}).get("body"),
        button_payload=message.get("button", {}).get("payload"),
        context_wamid=message.get("context", {}).get("id"),
        received_at=int(message["timestamp"]),
    )
