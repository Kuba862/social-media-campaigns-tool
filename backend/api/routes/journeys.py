"""Journeys: drafts, published versions, runs for contacts, listing and cancelling runs."""

from datetime import UTC, datetime
from typing import Annotated, Any, Literal, Self

from fastapi import APIRouter, Body, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from api.auth import current_user
from api.db import Database, Row
from api.deps import Db, Runs
from core.journey_schema import JourneyDefinition
from core.validation import validate
from storage.postgrest import ConflictError
from worker.workflows.journey import JourneyRunInput

router = APIRouter(prefix="/journeys", tags=["journeys"], dependencies=[Depends(current_user)])
runs_router = APIRouter(prefix="/runs", tags=["journeys"], dependencies=[Depends(current_user)])


class JourneyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)


class StartRuns(BaseModel):
    """Contacts by id, or by E.164 phone number (the panel's way); at least one of the two."""

    model_config = ConfigDict(extra="forbid")

    contact_ids: list[str] = Field(default_factory=list, max_length=500)
    phones: list[str] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def _some_target(self) -> Self:
        if not self.contact_ids and not self.phones:
            raise ValueError("contact_ids or phones required")
        return self


class Point(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    y: float


class DraftDefinition(BaseModel):
    """The editor's work in progress: only the shape is checked here, the content at publish."""

    model_config = ConfigDict(extra="allow")

    schema_version: Literal[1]
    nodes: list[dict[str, Any]] = Field(max_length=50)
    edges: list[dict[str, Any]] = Field(max_length=200)


class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    definition: DraftDefinition
    layout: dict[str, Point] = Field(default_factory=dict)  # node id -> canvas position


def _now() -> str:
    return datetime.now(UTC).isoformat()


@router.get("")
async def list_journeys(db: Db) -> list[Row]:
    """Each journey with its version numbers and publish dates embedded, for the panel's list."""
    return await db.select("journeys", columns="*,journey_versions(id,version,published_at)")


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_journey(body: JourneyCreate, db: Db) -> Row:
    return await db.insert("journeys", {"name": body.name, "status": "draft"})


@router.get("/{journey_id}")
async def get_journey(journey_id: str, db: Db) -> Row:
    """The journey with every version, oldest first; the draft is the one without published_at."""
    journey = await _journey(db, journey_id)
    return {**journey, "versions": await _versions(db, journey_id)}


@router.put("/{journey_id}/draft")
async def save_draft(journey_id: str, body: Draft, db: Db) -> Row:
    """Create or overwrite the journey's single draft; it takes the next version number."""
    await _journey(db, journey_id)
    versions = await _versions(db, journey_id)
    changes = {
        "definition": body.definition.model_dump(),
        "layout": {node_id: point.model_dump() for node_id, point in body.layout.items()},
    }
    draft = _draft_of(versions)
    if draft is not None:
        return await db.update("journey_versions", draft["id"], changes)
    number = max((v["version"] for v in versions), default=0) + 1
    return await db.insert(
        "journey_versions",
        {"journey_id": journey_id, "version": number, "published_at": None, **changes},
    )


@router.post("/{journey_id}/publish")
async def publish_draft(journey_id: str, db: Db) -> Row:
    """Schema and graph rules on the draft; it keeps its number and becomes immutable."""
    await _journey(db, journey_id)
    draft = _draft_of(await _versions(db, journey_id))
    if draft is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "journey has no draft")
    await _check(db, draft["definition"])
    row = await db.update("journey_versions", draft["id"], {"published_at": _now()})
    await db.update("journeys", journey_id, {"status": "active"})
    return row


@router.post("/{journey_id}/versions", status_code=status.HTTP_201_CREATED)
async def publish_version(
    journey_id: str, definition: Annotated[dict[str, Any], Body()], db: Db
) -> Row:
    """For API clients: schema check, graph rules, then an immutable version in one call."""
    await _journey(db, journey_id)
    await _check(db, definition)
    versions = await _versions(db, journey_id)
    number = max((v["version"] for v in versions), default=0) + 1
    row = await db.insert(
        "journey_versions",
        {
            "journey_id": journey_id,
            "version": number,
            "definition": definition,
            "published_at": _now(),
        },
    )
    await db.update("journeys", journey_id, {"status": "active"})
    return row


@router.delete("/{journey_id}/versions/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_version(journey_id: str, version_id: str, db: Db) -> Response:
    """Drafts and unused published versions can go; a version with runs is history and stays.
    When the last published version goes, the journey is a draft again."""
    await _journey(db, journey_id)
    versions = await _versions(db, journey_id)
    if not any(v["id"] == version_id for v in versions):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "version not found")
    if await db.select("journey_runs", journey_version_id=f"eq.{version_id}"):
        raise HTTPException(status.HTTP_409_CONFLICT, "version has runs and cannot be deleted")
    await db.delete("journey_versions", version_id)
    if not any(v.get("published_at") for v in versions if v["id"] != version_id):
        await db.update("journeys", journey_id, {"status": "draft"})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{journey_id}/runs", status_code=status.HTTP_201_CREATED)
async def start_runs(journey_id: str, body: StartRuns, db: Db, runs: Runs) -> dict[str, list[str]]:
    """One queued run per contact on the latest published version; the worker starts them.

    A contact already queued or running in this journey is skipped (partial unique index).
    """
    journey = await _journey(db, journey_id)
    published = [v for v in await _versions(db, journey_id) if v.get("published_at")]
    if journey["status"] != "active" or not published:
        raise HTTPException(status.HTTP_409_CONFLICT, "journey has no published version")
    latest = published[-1]
    contact_ids, unknown = await _resolve(db, body)
    started: list[str] = []
    skipped: list[str] = []
    for contact_id in contact_ids:
        workflow_id = f"journey:{journey_id}:contact:{contact_id}"
        try:
            run = await db.insert(
                "journey_runs",
                {
                    "journey_id": journey_id,
                    "journey_version_id": latest["id"],
                    "contact_id": contact_id,
                    "workflow_id": workflow_id,
                    "status": "queued",
                    "current_node_id": "start",
                },
            )
        except ConflictError:
            skipped.append(contact_id)
            continue
        await runs.start(
            workflow_id,
            JourneyRunInput(run["id"], journey_id, latest["id"], contact_id, latest["definition"]),
        )
        started.append(run["id"])
    return {"started": started, "skipped": skipped, "unknown": unknown}


@router.get("/{journey_id}/runs")
async def list_runs(journey_id: str, db: Db) -> list[Row]:
    return await db.select(
        "journey_runs", columns="*,contacts(phone_e164)", journey_id=f"eq.{journey_id}"
    )


@runs_router.get("")
async def list_all_runs(db: Db) -> list[Row]:
    """Every run across journeys, newest first; the home page's campaign overview reads this."""
    return await db.select("journey_runs", columns="*,contacts(phone_e164),journeys(name)")


@runs_router.get("/{run_id}")
async def get_run(run_id: str, db: Db, runs: Runs) -> Row:
    """The stored row, plus the live node and waiting reason when the engine can tell."""
    row = await _run(db, run_id)
    if row["status"] == "running":
        live = await runs.state(row["workflow_id"])
        if live:
            row = {**row, "live": live}
    return row


@runs_router.post("/{run_id}/cancel")
async def cancel_run(run_id: str, db: Db, runs: Runs) -> Row:
    row = await _run(db, run_id)
    if row["status"] not in ("queued", "running"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"run is {row['status']}, not running")
    await runs.cancel(row["workflow_id"])
    return await db.update("journey_runs", run_id, {"status": "cancelled", "ended_at": _now()})


async def _resolve(db: Database, body: StartRuns) -> tuple[list[str], list[str]]:
    """Contact ids to start, and the phone numbers no contact has."""
    contact_ids = list(body.contact_ids)
    unknown: list[str] = []
    if body.phones:
        quoted = ",".join(f'"{phone}"' for phone in body.phones)
        found = await db.select("contacts", phone_e164=f"in.({quoted})")
        by_phone = {row["phone_e164"]: row["id"] for row in found}
        for phone in body.phones:
            if phone in by_phone:
                contact_ids.append(by_phone[phone])
            else:
                unknown.append(phone)
    return contact_ids, unknown


async def _check(db: Database, definition: dict[str, Any]) -> None:
    """Schema, then graph rules against APPROVED templates; 422 carries the list of problems."""
    try:
        parsed = JourneyDefinition.model_validate(definition)
    except ValidationError as exc:
        problems = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, problems) from exc
    approved = {t["id"] for t in await db.select("templates", status="eq.APPROVED")}
    errors = validate(parsed, approved)
    if errors:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, errors)


async def _versions(db: Database, journey_id: str) -> list[Row]:
    rows = await db.select("journey_versions", journey_id=f"eq.{journey_id}")
    return sorted(rows, key=lambda v: int(v["version"]))


def _draft_of(versions: list[Row]) -> Row | None:
    return next((v for v in versions if v.get("published_at") is None), None)


async def _journey(db: Database, journey_id: str) -> Row:
    rows = await db.select("journeys", id=f"eq.{journey_id}")
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "journey not found")
    return rows[0]


async def _run(db: Database, run_id: str) -> Row:
    rows = await db.select("journey_runs", id=f"eq.{run_id}")
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    return rows[0]
