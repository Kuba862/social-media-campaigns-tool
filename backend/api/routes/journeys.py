"""Journeys: create, publish a validated version, start runs for contacts, list and cancel runs."""

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from api.auth import current_user
from api.db import Database, Row
from api.deps import Db, Runs
from api.temporal import RunAlreadyActive
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
    model_config = ConfigDict(extra="forbid")

    contact_ids: list[str] = Field(min_length=1, max_length=500)


def _now() -> str:
    return datetime.now(UTC).isoformat()


@router.get("")
async def list_journeys(db: Db) -> list[Row]:
    return await db.select("journeys")


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_journey(body: JourneyCreate, db: Db) -> Row:
    return await db.insert("journeys", {"name": body.name, "status": "draft"})


@router.post("/{journey_id}/versions", status_code=status.HTTP_201_CREATED)
async def publish_version(
    journey_id: str, definition: Annotated[dict[str, Any], Body()], db: Db
) -> Row:
    """Schema check, then graph rules against APPROVED templates, then an immutable version."""
    await _journey(db, journey_id)
    try:
        parsed = JourneyDefinition.model_validate(definition)
    except ValidationError as exc:
        problems = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, problems) from exc
    approved = {t["id"] for t in await db.select("templates", status="eq.APPROVED")}
    errors = validate(parsed, approved)
    if errors:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, errors)
    versions = await db.select("journey_versions", journey_id=f"eq.{journey_id}")
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


@router.post("/{journey_id}/runs", status_code=status.HTTP_201_CREATED)
async def start_runs(journey_id: str, body: StartRuns, db: Db, runs: Runs) -> dict[str, list[str]]:
    """One run per contact on the latest version; a contact already in this journey is skipped."""
    journey = await _journey(db, journey_id)
    versions = await db.select("journey_versions", journey_id=f"eq.{journey_id}")
    if journey["status"] != "active" or not versions:
        raise HTTPException(status.HTTP_409_CONFLICT, "journey has no published version")
    latest = max(versions, key=lambda v: int(v["version"]))
    started: list[str] = []
    skipped: list[str] = []
    for contact_id in body.contact_ids:
        workflow_id = f"journey:{journey_id}:contact:{contact_id}"
        try:
            run = await db.insert(
                "journey_runs",
                {
                    "journey_id": journey_id,
                    "journey_version_id": latest["id"],
                    "contact_id": contact_id,
                    "workflow_id": workflow_id,
                    "status": "running",
                    "current_node_id": "start",
                },
            )
        except ConflictError:
            skipped.append(contact_id)
            continue
        try:
            await runs.start(
                workflow_id,
                JourneyRunInput(
                    run["id"], journey_id, latest["id"], contact_id, latest["definition"]
                ),
            )
        except RunAlreadyActive:
            await db.update("journey_runs", run["id"], {"status": "cancelled", "ended_at": _now()})
            skipped.append(contact_id)
            continue
        started.append(run["id"])
    return {"started": started, "skipped": skipped}


@router.get("/{journey_id}/runs")
async def list_runs(journey_id: str, db: Db) -> list[Row]:
    return await db.select(
        "journey_runs", columns="*,contacts(phone_e164)", journey_id=f"eq.{journey_id}"
    )


@runs_router.get("/{run_id}")
async def get_run(run_id: str, db: Db, runs: Runs) -> Row:
    """The stored row, plus the live node and waiting reason while the workflow runs."""
    row = await _run(db, run_id)
    if row["status"] == "running":
        row = {**row, "live": await runs.state(row["workflow_id"])}
    return row


@runs_router.post("/{run_id}/cancel")
async def cancel_run(run_id: str, db: Db, runs: Runs) -> Row:
    row = await _run(db, run_id)
    if row["status"] != "running":
        raise HTTPException(status.HTTP_409_CONFLICT, f"run is {row['status']}, not running")
    await runs.cancel(row["workflow_id"])
    return await db.update("journey_runs", run_id, {"status": "cancelled", "ended_at": _now()})


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
