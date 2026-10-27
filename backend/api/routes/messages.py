"""Messages: a single test send to an allow-listed number, and the log the panel reads."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from api.auth import current_user
from api.db import Database, Row
from api.deps import AppSettings, Db, Meta
from core.consent import has_active_consent
from core.sending import recipient_allowed
from meta_client import MetaError, MetaPermanentError

router = APIRouter(prefix="/messages", tags=["messages"], dependencies=[Depends(current_user)])

LOG_COLUMNS = (
    "*,templates(name,language),contacts(phone_e164),message_events(type,occurred_at,payload)"
)


class TestSendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str
    to_e164: str = Field(pattern=r"^\+[1-9]\d{6,14}$")
    body_values: list[str] = Field(default_factory=list)


@router.get("")
async def list_messages(db: Db) -> list[Row]:
    return await db.select("messages", columns=LOG_COLUMNS)


@router.post("/test", status_code=status.HTTP_201_CREATED)
async def send_test(request: TestSendRequest, db: Db, meta: Meta, settings: AppSettings) -> Row:
    template = await _approved_template(db, request.template_id)
    allowed = recipient_allowed(
        request.to_e164, settings.wa_send_mode, settings.wa_allowed_test_recipients
    )
    if not allowed:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "recipient is not in WA_ALLOWED_TEST_RECIPIENTS"
        )
    contact = await db.upsert("contacts", {"phone_e164": request.to_e164}, on_conflict="phone_e164")
    consents = await db.select("consents", contact_id=f"eq.{contact['id']}")
    if not has_active_consent(consents):
        consent = {"contact_id": contact["id"], "status": "opted_in", "source": "test_allowlist"}
        await db.insert("consents", consent)
    message = await db.insert(
        "messages",
        {
            "run_id": None,
            "node_id": "test",
            "contact_id": contact["id"],
            "template_id": template["id"],
            "idempotency_key": f"test:{uuid4()}",
            "status": "pending",
        },
    )
    try:
        result = await meta.send_template(
            request.to_e164, template["name"], template["language"], request.body_values
        )
    except MetaError as exc:
        error = {"message": str(exc), "code": exc.code, "subcode": exc.subcode}
        await db.update("messages", message["id"], {"status": "failed", "error": error})
        if isinstance(exc, MetaPermanentError):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return await db.update(
        "messages",
        message["id"],
        {"wamid": result.wamid, "status": "sent", "meta_response": result.raw},
    )


async def _approved_template(db: Database, template_id: str) -> Row:
    rows = await db.select("templates", id=f"eq.{template_id}")
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "template not found")
    if rows[0]["status"] != "APPROVED":
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"template is {rows[0]['status']}, not APPROVED"
        )
    return rows[0]
