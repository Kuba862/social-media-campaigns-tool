"""FastAPI app: /healthz is open, everything else goes through api.auth.CurrentUser."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from api.auth import CurrentUser
from api.db import Database
from api.routes.templates import router as templates_router
from api.routes.webhooks_meta import router as webhooks_router
from api.settings import load_settings
from meta_client import MetaClient


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


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/me")
async def me(user: CurrentUser) -> dict[str, str]:
    """Smoke test for auth: tells you who Supabase says you are."""
    return {"id": user.id, "email": user.email}
