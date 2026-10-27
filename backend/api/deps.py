"""FastAPI dependencies handing out the per-process objects created in lifespan."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from api.db import Database
from api.dispatch import QueuedRuns
from api.settings import Settings
from api.temporal import AllRuns
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


def get_meta_or_none(request: Request) -> MetaClient | None:
    meta: MetaClient | None = request.app.state.meta
    return meta


AppSettings = Annotated[Settings, Depends(get_settings)]
Db = Annotated[Database, Depends(get_db)]
Meta = Annotated[MetaClient, Depends(get_meta)]
OptionalMeta = Annotated[MetaClient | None, Depends(get_meta_or_none)]


def get_runs(db: Db) -> AllRuns:
    """Commands for the workflow engine go through the queue; the worker executes them."""
    return QueuedRuns(db)


def get_runs_or_none(db: Db) -> AllRuns | None:
    """Kept for the webhook: the queue is always available, so this never yields None now."""
    return QueuedRuns(db)


Runs = Annotated[AllRuns, Depends(get_runs)]
OptionalRuns = Annotated[AllRuns | None, Depends(get_runs_or_none)]
