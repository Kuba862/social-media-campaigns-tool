"""FastAPI dependencies handing out the per-process objects created in lifespan."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from api.db import Database
from api.settings import Settings
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


AppSettings = Annotated[Settings, Depends(get_settings)]
Db = Annotated[Database, Depends(get_db)]
Meta = Annotated[MetaClient, Depends(get_meta)]
