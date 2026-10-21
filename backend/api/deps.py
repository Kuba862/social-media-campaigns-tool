"""FastAPI dependencies handing out the per-process objects created in lifespan."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from temporalio.service import RPCError

from api.db import Database
from api.settings import Settings
from api.temporal import JourneyRuns, connect
from meta_client import MetaClient


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_db(request: Request) -> Database:
    db: Database = request.app.state.db
    return db


def get_meta(request: Request) -> MetaClient:
    meta: MetaClient | None = request.app.state.meta
    if meta is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Meta is not configured (META_SYSTEM_USER_TOKEN)"
        )
    return meta


async def get_runs(request: Request) -> JourneyRuns:
    """Connects to Temporal on first use and keeps the client for the process."""
    runs: JourneyRuns | None = request.app.state.runs
    if runs is None:
        try:
            runs = await connect(request.app.state.settings)
        except RPCError as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "Temporal unavailable"
            ) from exc
        request.app.state.runs = runs
    return runs


async def get_runs_or_none(request: Request) -> JourneyRuns | None:
    """For the webhook: persist first, signal if Temporal is reachable, never fail the request."""
    try:
        return await get_runs(request)
    except HTTPException:
        return None


AppSettings = Annotated[Settings, Depends(get_settings)]
Db = Annotated[Database, Depends(get_db)]
Meta = Annotated[MetaClient, Depends(get_meta)]
Runs = Annotated[JourneyRuns, Depends(get_runs)]
OptionalRuns = Annotated[JourneyRuns | None, Depends(get_runs_or_none)]
