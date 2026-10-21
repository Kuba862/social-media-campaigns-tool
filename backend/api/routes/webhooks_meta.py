"""Meta webhooks: the only unauthenticated route, protected by the X-Hub-Signature-256 check."""

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import PlainTextResponse

from api.db import Database, Row
from api.deps import AppSettings, Db
from api.settings import Settings
from meta_client import (
    InboundMessageEvent,
    MessageStatusEvent,
    TemplateStatusEvent,
    parse_webhook,
    signature_is_valid,
)

router = APIRouter(prefix="/webhooks/meta", tags=["webhooks"])

OPT_OUT_KEYWORDS = frozenset({"stop", "unsubscribe", "cancel", "quit", "end"})


def _configured(settings: Settings) -> None:
    if not settings.meta_app_secret or not settings.meta_webhook_verify_token:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "webhook is not configured")


@router.get("")
async def verify(request: Request, settings: AppSettings) -> PlainTextResponse:
    """Meta's one-time handshake: echo hub.challenge when the verify token matches."""
    _configured(settings)
    params = request.query_params
    token_ok = params.get("hub.verify_token") == settings.meta_webhook_verify_token
    if params.get("hub.mode") != "subscribe" or not token_ok:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "verification failed")
    return PlainTextResponse(params.get("hub.challenge", ""))


@router.post("")
async def receive(request: Request, settings: AppSettings, db: Db) -> dict[str, int]:
    """Verify, persist, answer 200. Meta retries anything else, so every write is idempotent."""
    _configured(settings)
    raw = await request.body()
    header = request.headers.get("x-hub-signature-256")
    if not signature_is_valid(settings.meta_app_secret, raw, header):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad signature")
    payload: dict[str, Any] = json.loads(raw)
    counts = {"template_status": 0, "message_status": 0, "inbound": 0}
    for event in parse_webhook(payload):
        if isinstance(event, TemplateStatusEvent):
            await _store_template_status(db, event)
        elif isinstance(event, MessageStatusEvent):
            await _store_message_status(db, event)
        else:
            await _store_inbound(db, event)
        counts[event.kind] += 1
    return counts


def _iso(unix_seconds: int) -> str:
    return datetime.fromtimestamp(unix_seconds, tz=UTC).isoformat()


async def _store_template_status(db: Database, event: TemplateStatusEvent) -> None:
    rows = await db.select("templates", name=f"eq.{event.name}", language=f"eq.{event.language}")
    if not rows:
        return  # a template we never created, e.g. made directly in WhatsApp Manager
    changes = {
        "meta_template_id": event.meta_template_id,
        "status": event.status,
        "rejection_reason": event.rejection_reason,
    }
    await db.update("templates", rows[0]["id"], changes)


async def _store_message_status(db: Database, event: MessageStatusEvent) -> None:
    messages = await db.select("messages", wamid=f"eq.{event.wamid}")
    message_id = messages[0]["id"] if messages else None
    stored = await db.insert_ignore(
        "message_events",
        {
            "message_id": message_id,
            "wamid": event.wamid,
            "type": event.status,
            "payload": event.model_dump(),
            "occurred_at": _iso(event.occurred_at),
        },
        on_conflict="wamid,type",
    )
    if stored is None or message_id is None:
        return  # duplicate delivery, or a message we do not know
    changes: Row = {"status": event.status}
    if event.error is not None:
        changes["error"] = event.error
    await db.update("messages", message_id, changes)


async def _store_inbound(db: Database, event: InboundMessageEvent) -> None:
    contact = await db.upsert(
        "contacts", {"phone_e164": event.from_phone}, on_conflict="phone_e164"
    )
    stored = await db.insert_ignore(
        "inbound_messages",
        {
            "contact_id": contact["id"],
            "wamid": event.wamid,
            "type": event.type,
            "text": event.text,
            "button_payload": event.button_payload,
            "context_wamid": event.context_wamid,
            "received_at": _iso(event.received_at),
        },
        on_conflict="wamid",
    )
    if stored is None:
        return  # duplicate delivery
    if (event.text or "").strip().lower() in OPT_OUT_KEYWORDS:
        consent = {"contact_id": contact["id"], "status": "opted_out", "source": "whatsapp_keyword"}
        await db.insert("consents", consent)
