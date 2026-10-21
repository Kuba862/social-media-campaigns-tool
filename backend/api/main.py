"""FastAPI app: /healthz is open, everything else goes through api.auth.CurrentUser."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.auth import CurrentUser
from api.db import Database
from api.routes.journeys import router as journeys_router
from api.routes.journeys import runs_router
from api.routes.messages import router as messages_router
from api.routes.sync import router as sync_router
from api.routes.templates import router as templates_router
from api.routes.webhooks_meta import router as webhooks_router
from api.settings import load_settings
from meta_client import MetaClient
from storage.postgrest import ConflictError, NotFoundError, StorageError, StorageUnavailable


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Runs once at startup (before yield) and once at shutdown (after)."""
    settings = load_settings()
    app.state.settings = settings
    app.state.http = httpx.AsyncClient(timeout=10.0)
    app.state.db = Database(app.state.http, settings)
    app.state.meta = (
        MetaClient(
            app.state.http,
            graph_version=settings.meta_graph_version,
            waba_id=settings.meta_waba_id,
            phone_number_id=settings.meta_phone_number_id,
            access_token=settings.meta_system_user_token,
        )
        if settings.meta_system_user_token
        else None
    )
    try:
        yield
    finally:
        await app.state.http.aclose()


app = FastAPI(title="WhatsApp campaigns API", lifespan=lifespan)
app.include_router(templates_router)
app.include_router(webhooks_router)
app.include_router(messages_router)
app.include_router(journeys_router)
app.include_router(runs_router)
app.include_router(sync_router)

STORAGE_STATUS: dict[type[StorageError], int] = {
    ConflictError: 409,
    NotFoundError: 404,
    StorageUnavailable: 503,
}


@app.exception_handler(StorageError)
async def storage_error(request: Request, exc: StorageError) -> JSONResponse:
    """Storage errors keep their old HTTP meaning; anything else from PostgREST is a 502."""
    code = next((code for kind, code in STORAGE_STATUS.items() if isinstance(exc, kind)), 502)
    return JSONResponse(status_code=code, content={"detail": str(exc)})


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/me")
async def me(user: CurrentUser) -> dict[str, str]:
    """Smoke test for auth: tells you who Supabase says you are."""
    return {"id": user.id, "email": user.email}
