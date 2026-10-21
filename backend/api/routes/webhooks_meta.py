"""Meta webhooks: the only unauthenticated route, protected by the X-Hub-Signature-256 check."""

import json
import logging
from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from temporalio.service import RPCError

from api.db import Database, Row
from api.deps import AppSettings, Db, OptionalRuns
from api.settings import Settings
from api.temporal import JourneyRuns
from meta_client import (
    InboundMessageEvent,
    MessageStatusEvent,
    TemplateStatusEvent,
    parse_webhook,
    signature_is_valid,
)
from worker.workflows.journey import ReplySignal

router = APIRouter(prefix="/webhooks/meta", tags=["webhooks"])

OPT_OUT_KEYWORDS = frozenset({"stop", "unsubscribe", "cancel", "quit", "end"})

log = logging.getLogger(__name__)


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
async def receive(
    request: Request, settings: AppSettings, db: Db, runs: OptionalRuns
) -> dict[str, int]:
    """Verify, persist, signal, answer 200. Meta retries anything else, so writes are idempotent."""
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
            await _store_message_status(db, runs, event)
        else:
            await _store_inbound(db, runs, event)
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


async def _store_message_status(
    db: Database, runs: JourneyRuns | None, event: MessageStatusEvent
) -> None:
    messages = await db.select("messages", wamid=f"eq.{event.wamid}")
    message = messages[0] if messages else None
    stored = await db.insert_ignore(
        "message_events",
        {
            "message_id": message["id"] if message else None,
            "wamid": event.wamid,
            "type": event.status,
            "payload": event.model_dump(),
            "occurred_at": _iso(event.occurred_at),
        },
        on_conflict="wamid,type",
    )
    if stored is None or message is None:
        return  # duplicate delivery, or a message we do not know
    changes: Row = {"status": event.status}
    if event.error is not None:
        changes["error"] = event.error
    await db.update("messages", message["id"], changes)
    if runs is not None and message.get("run_id"):
        for run in await _running(db, id=f"eq.{message['run_id']}"):
            await _signal(runs.signal_status(run["workflow_id"], event.model_dump()))


async def _store_inbound(
    db: Database, runs: JourneyRuns | None, event: InboundMessageEvent
) -> None:
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
    opted_out = (event.text or "").strip().lower() in OPT_OUT_KEYWORDS
    if opted_out:
        consent = {"contact_id": contact["id"], "status": "opted_out", "source": "whatsapp_keyword"}
        await db.insert("consents", consent)
    if runs is None:
        log.warning("Temporal unreachable, inbound %s stored without signalling", event.wamid)
        return
    reply = ReplySignal(
        wamid=event.wamid,
        text=event.text,
        button_payload=event.button_payload,
        context_wamid=event.context_wamid,
    )
    for run in await _target_runs(db, contact["id"], event.context_wamid):
        await _signal(runs.signal_reply(run["workflow_id"], reply))
    if opted_out:
        for run in await _running(db, contact_id=f"eq.{contact['id']}"):
            await _signal(runs.signal_opt_out(run["workflow_id"]))


async def _target_runs(db: Database, contact_id: str, context_wamid: str | None) -> list[Row]:
    """The run that sent context_wamid when known; otherwise every running run of the contact."""
    if context_wamid:
        sent = await db.select("messages", wamid=f"eq.{context_wamid}")
        if sent and sent[0].get("run_id"):
            return await _running(db, id=f"eq.{sent[0]['run_id']}")
    return await _running(db, contact_id=f"eq.{contact_id}")


async def _running(db: Database, **filters: str) -> list[Row]:
    return await db.select("journey_runs", status="eq.running", **filters)


async def _signal(call: Awaitable[None]) -> None:
    """Signalling is best effort: the event is already stored, Meta must get its 200."""
    try:
        await call
    except RPCError:
        log.warning("signal to Temporal failed", exc_info=True)
