"""Sync connectors: register one, run it now, put it on a Temporal Schedule, list the runs."""

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.auth import current_user
from api.db import Database, Row
from api.deps import Db, OptionalRuns, Runs
from api.temporal import schedule_id
from sync.connectors import BUILDERS

router = APIRouter(prefix="/sync", tags=["sync"], dependencies=[Depends(current_user)])

FIVE_FIELDS = re.compile(r"^\S+(?:\s+\S+){4}$")  # Temporal validates the expression itself


class ConnectorSpec(BaseModel):
    """The row without the name: how often, whether, and the connector's config (no secrets)."""

    model_config = ConfigDict(extra="forbid")

    schedule_cron: str
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("schedule_cron")
    @classmethod
    def _five_fields(cls, value: str) -> str:
        if not FIVE_FIELDS.match(value.strip()):
            raise ValueError("schedule_cron needs five fields, e.g. '0 * * * *'")
        return value.strip()


@router.get("/connectors")
async def list_connectors(db: Db, runs: OptionalRuns) -> list[Row]:
    """Rows plus the live schedule (paused, next run) when Temporal is reachable."""
    rows = await db.select("sync_connectors")
    result: list[Row] = []
    for row in rows:
        schedule = await runs.schedule_info(row["name"]) if runs is not None else None
        result.append({**row, "schedule": schedule})
    return result


@router.put("/connectors/{name}")
async def register_connector(name: str, body: ConnectorSpec, db: Db) -> Row:
    """Create or update the row; the name must be a connector module from the registry."""
    if name not in BUILDERS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"unknown connector {name}; known: {', '.join(sorted(BUILDERS))}",
        )
    row = {
        "name": name,
        "schedule_cron": body.schedule_cron,
        "enabled": body.enabled,
        "config": body.config,
    }
    return await db.upsert("sync_connectors", row, on_conflict="name")


@router.post("/connectors/{name}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_now(name: str, db: Db, runs: Runs) -> dict[str, str]:
    await _connector(db, name)
    return {"workflow_id": await runs.start_sync(name)}


@router.post("/connectors/{name}/schedule")
async def apply_schedule(name: str, db: Db, runs: Runs) -> dict[str, Any]:
    """Push the row's cron and enabled flag to Temporal; disabled means a paused schedule."""
    row = await _connector(db, name)
    await runs.apply_schedule(name, row["schedule_cron"], bool(row["enabled"]))
    return {"schedule_id": schedule_id(name), **(await runs.schedule_info(name) or {})}


@router.get("/runs")
async def list_runs(db: Db, connector: str | None = None) -> list[Row]:
    filters: dict[str, str] = {}
    if connector:
        filters["connector_id"] = f"eq.{(await _connector(db, connector))['id']}"
    return await db.select("sync_runs", columns="*,sync_connectors(name)", **filters)


async def _connector(db: Database, name: str) -> Row:
    rows = await db.select("sync_connectors", name=f"eq.{name}")
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"connector {name} is not registered")
    return rows[0]
