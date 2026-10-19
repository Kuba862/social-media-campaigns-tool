"""FastAPI app: /healthz is open, everything else goes through api.auth.CurrentUser."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from api.auth import CurrentUser
from api.settings import load_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Runs once at startup (before yield) and once at shutdown (after)."""
    app.state.settings = load_settings()
    app.state.http = httpx.AsyncClient(timeout=10.0)
    try:
        yield
    finally:
        await app.state.http.aclose()


app = FastAPI(title="WhatsApp campaigns API", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/me")
async def me(user: CurrentUser) -> dict[str, str]:
    """Smoke test for auth: tells you who Supabase says you are."""
    return {"id": user.id, "email": user.email}
