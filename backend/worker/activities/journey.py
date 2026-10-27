"""Activities behind JourneyWorkflow: every side effect of a journey lives here (guide 4.2, 4.3)."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from temporalio import activity
from temporalio.exceptions import ApplicationError

from core.consent import has_active_consent
from core.sending import recipient_allowed
from meta_client import MetaPermanentError, SendResult
from meta_client.errors import RE_ENGAGEMENT_CODE
from storage.postgrest import Row, Storage

TERMINAL_RUN_STATUSES = frozenset(
    {"completed", "failed", "cancelled", "skipped_no_consent", "opted_out"}
)
SERVICE_WINDOW = timedelta(hours=24)  # Meta's customer service window after an inbound message
WINDOW_CLOSED = "customer service window is closed (no inbound message in the last 24 hours)"


@dataclass(frozen=True)
class ContactSnapshot:
    """What the workflow may read as `contact.*` in conditions and template variables."""

    id: str
    phone_e164: str
    first_name: str | None
    locale: str | None
    country: str | None
    attributes: dict[str, Any]
    external_ref: str | None


@dataclass(frozen=True)
class SendTemplateInput:
    run_id: str
    workflow_id: str
    node_id: str
    visit: int  # how many times the workflow has reached this node, for looping journeys
    contact_id: str
    template_id: str
    body_values: list[str] = field(default_factory=list)

    @property
    def idempotency_key(self) -> str:
        return f"{self.workflow_id}:{self.node_id}:{self.visit}"


@dataclass(frozen=True)
class SendTextInput:
    """A service message for a send_text node; the same idempotency key shape as templates."""

    run_id: str
    workflow_id: str
    node_id: str
    visit: int
    contact_id: str
    text: str  # already rendered by the workflow
    if_closed: str = "skip"  # "skip" (go on) or "fail" (end the run) when the window is closed

    @property
    def idempotency_key(self) -> str:
        return f"{self.workflow_id}:{self.node_id}:{self.visit}"


@dataclass(frozen=True)
class SendTemplateResult:
    """Outcome of send_template and send_text alike."""

    message_id: str
    status: str  # "sent", "failed" or "skipped" (text node outside the window)
    wamid: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class RunProgress:
    run_id: str
    current_node_id: str
    status: str | None = None  # set when the run ends


class MessageSender(Protocol):
    """The Meta calls the activities need; MetaClient and the test double both satisfy it."""

    async def send_template(
        self, to_e164: str, template_name: str, language: str, body_values: list[str]
    ) -> SendResult: ...

    async def send_text(self, to_e164: str, text: str) -> SendResult: ...


class JourneyActivities:
    """Holds the clients; register with Worker(activities=JourneyActivities(...).all())."""

    def __init__(
        self,
        db: Storage,
        meta: MessageSender | None,
        *,
        send_mode: str,
        allowlist: Iterable[str],
    ) -> None:
        self._db = db
        self._meta = meta
        self._send_mode = send_mode
        self._allowlist = frozenset(allowlist)

    def all(self) -> list[Callable[..., Any]]:
        return [
            self.load_contact,
            self.check_consent,
            self.send_template,
            self.send_text,
            self.update_contact,
            self.record_run_progress,
        ]

    @activity.defn
    async def load_contact(self, contact_id: str) -> ContactSnapshot:
        return await self._contact(contact_id)

    @activity.defn
    async def check_consent(self, contact_id: str) -> bool:
        consents = await self._db.select("consents", contact_id=f"eq.{contact_id}")
        return has_active_consent(consents)

    @activity.defn
    async def send_template(self, request: SendTemplateInput) -> SendTemplateResult:
        """Guide 4.3: insert first, reuse an existing wamid, call Meta once, store the wamid."""
        message = await self._db.insert_ignore(
            "messages",
            {
                "run_id": request.run_id,
                "node_id": request.node_id,
                "contact_id": request.contact_id,
                "template_id": request.template_id,
                "idempotency_key": request.idempotency_key,
                "status": "pending",
            },
            on_conflict="idempotency_key",
        )
        if message is None:
            existing = await self._db.select(
                "messages", idempotency_key=f"eq.{request.idempotency_key}"
            )
            message = existing[0]
            if message.get("wamid"):
                return SendTemplateResult(message["id"], "sent", wamid=message["wamid"])
        template = await self._template(request.template_id)
        contact = await self._contact(request.contact_id)
        if template["status"] != "APPROVED":
            return await self._fail(
                message["id"], f"template {template['name']} is {template['status']}"
            )
        if not recipient_allowed(contact.phone_e164, self._send_mode, self._allowlist):
            return await self._fail(message["id"], "recipient is not in WA_ALLOWED_TEST_RECIPIENTS")
        if self._meta is None:
            raise ApplicationError(
                "Meta is not configured (META_SYSTEM_USER_TOKEN)", non_retryable=True
            )
        try:
            result = await self._meta.send_template(
                contact.phone_e164, template["name"], template["language"], request.body_values
            )
        except MetaPermanentError as exc:
            return await self._fail(message["id"], str(exc), code=exc.code)
        # MetaTransientError propagates: Temporal retries the activity with backoff.
        updated = await self._db.update(
            "messages",
            message["id"],
            {"wamid": result.wamid, "status": "sent", "meta_response": result.raw},
        )
        return SendTemplateResult(updated["id"], "sent", wamid=result.wamid)

    @activity.defn
    async def send_text(self, request: SendTextInput) -> SendTemplateResult:
        """A service message, insert-first like send_template. The 24-hour window is checked here
        from inbound_messages and again by Meta (code 131047); a closed window skips or fails the
        node as the definition says, never retries."""
        message = await self._db.insert_ignore(
            "messages",
            {
                "run_id": request.run_id,
                "node_id": request.node_id,
                "contact_id": request.contact_id,
                "template_id": None,
                "kind": "text",
                "text": request.text,
                "idempotency_key": request.idempotency_key,
                "status": "pending",
            },
            on_conflict="idempotency_key",
        )
        if message is None:
            existing = await self._db.select(
                "messages", idempotency_key=f"eq.{request.idempotency_key}"
            )
            message = existing[0]
            if message.get("wamid"):
                return SendTemplateResult(message["id"], "sent", wamid=message["wamid"])
            if message.get("status") == "skipped":
                return SendTemplateResult(message["id"], "skipped", error=WINDOW_CLOSED)
        contact = await self._contact(request.contact_id)
        if not recipient_allowed(contact.phone_e164, self._send_mode, self._allowlist):
            return await self._fail(message["id"], "recipient is not in WA_ALLOWED_TEST_RECIPIENTS")
        if not await self._window_open(request.contact_id):
            return await self._window_closed(message["id"], request.if_closed)
        if self._meta is None:
            raise ApplicationError(
                "Meta is not configured (META_SYSTEM_USER_TOKEN)", non_retryable=True
            )
        try:
            result = await self._meta.send_text(contact.phone_e164, request.text)
        except MetaPermanentError as exc:
            if exc.code == RE_ENGAGEMENT_CODE:
                return await self._window_closed(message["id"], request.if_closed)
            return await self._fail(message["id"], str(exc), code=exc.code)
        updated = await self._db.update(
            "messages",
            message["id"],
            {"wamid": result.wamid, "status": "sent", "meta_response": result.raw},
        )
        return SendTemplateResult(updated["id"], "sent", wamid=result.wamid)

    @activity.defn
    async def update_contact(self, contact_id: str, changes: dict[str, Any]) -> None:
        """Keys like "attributes.x" merge into the attributes JSON; other keys are columns."""
        contact = await self._contact(contact_id)
        attributes = dict(contact.attributes)
        columns: dict[str, Any] = {}
        for key, value in changes.items():
            if key.startswith("attributes."):
                attributes[key.removeprefix("attributes.")] = value
            else:
                columns[key] = value
        await self._db.update("contacts", contact_id, {**columns, "attributes": attributes})

    @activity.defn
    async def record_run_progress(self, progress: RunProgress) -> None:
        changes: dict[str, Any] = {"current_node_id": progress.current_node_id}
        if progress.status is not None:
            changes["status"] = progress.status
            if progress.status in TERMINAL_RUN_STATUSES:
                changes["ended_at"] = datetime.now(UTC).isoformat()
        await self._db.update("journey_runs", progress.run_id, changes)

    async def _contact(self, contact_id: str) -> ContactSnapshot:
        rows = await self._db.select("contacts", id=f"eq.{contact_id}")
        if not rows:
            raise ApplicationError(f"contact {contact_id} not found", non_retryable=True)
        row = rows[0]
        return ContactSnapshot(
            id=row["id"],
            phone_e164=row["phone_e164"],
            first_name=row.get("first_name"),
            locale=row.get("locale"),
            country=row.get("country"),
            attributes=row.get("attributes") or {},
            external_ref=row.get("external_ref"),
        )

    async def _template(self, template_id: str) -> Row:
        rows = await self._db.select("templates", id=f"eq.{template_id}")
        if not rows:
            raise ApplicationError(f"template {template_id} not found", non_retryable=True)
        return rows[0]

    async def _window_open(self, contact_id: str) -> bool:
        """True when the contact wrote to us within the last 24 hours."""
        rows = await self._db.select(
            "inbound_messages", contact_id=f"eq.{contact_id}", order="received_at.desc"
        )
        stamps = [
            datetime.fromisoformat(str(r["received_at"])) for r in rows if r.get("received_at")
        ]
        if not stamps:
            return False
        latest = max(s if s.tzinfo else s.replace(tzinfo=UTC) for s in stamps)
        return datetime.now(UTC) - latest < SERVICE_WINDOW

    async def _window_closed(self, message_id: str, policy: str) -> SendTemplateResult:
        if policy == "fail":
            return await self._fail(message_id, WINDOW_CLOSED)
        await self._db.update(
            "messages", message_id, {"status": "skipped", "error": {"message": WINDOW_CLOSED}}
        )
        return SendTemplateResult(message_id, "skipped", error=WINDOW_CLOSED)

    async def _fail(
        self, message_id: str, error: str, code: int | None = None
    ) -> SendTemplateResult:
        await self._db.update(
            "messages", message_id, {"status": "failed", "error": {"message": error, "code": code}}
        )
        return SendTemplateResult(message_id, "failed", error=error)
