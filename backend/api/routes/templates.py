"""Templates: drafts live in our table, submit sends them to Meta, sync pulls Meta's verdict."""

from fastapi import APIRouter, Depends, HTTPException, status

from api.auth import current_user
from api.db import Row
from api.deps import AppSettings, Db, Meta
from meta_client import MetaPermanentError, MetaTransientError, TemplateSpec

router = APIRouter(prefix="/templates", tags=["templates"], dependencies=[Depends(current_user)])


@router.get("")
async def list_templates(db: Db) -> list[Row]:
    return await db.select("templates")


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_template(spec: TemplateSpec, db: Db, settings: AppSettings) -> Row:
    """Saves a DRAFT. Nothing goes to Meta until /submit."""
    return await db.insert(
        "templates",
        {
            "waba_id": settings.meta_waba_id,
            "name": spec.name,
            "language": spec.language,
            "category": spec.category,
            "components": spec.model_dump(include={"body", "example_values", "quick_replies"}),
            "status": "DRAFT",
        },
    )


@router.post("/{template_id}/submit")
async def submit_template(template_id: str, db: Db, meta: Meta) -> Row:
    row = await _get(db, template_id)
    if row["status"] != "DRAFT":
        raise HTTPException(status.HTTP_409_CONFLICT, f"template is {row['status']}, not DRAFT")
    spec = TemplateSpec(
        name=row["name"], language=row["language"], category=row["category"], **row["components"]
    )
    try:
        created = await meta.create_template(spec)
    except MetaPermanentError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except MetaTransientError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    changes = {"meta_template_id": created.meta_template_id, "status": created.status}
    return await db.update("templates", template_id, changes)


@router.post("/{template_id}/sync")
async def sync_template(template_id: str, db: Db, meta: Meta) -> Row:
    """Asks Meta for the current verdict; the webhook (next step) will make this automatic."""
    row = await _get(db, template_id)
    try:
        state = await meta.get_template_state(row["name"], row["language"])
    except MetaTransientError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Meta has no such template")
    changes = {
        "meta_template_id": state.meta_template_id,
        "status": state.status,
        "rejection_reason": state.rejection_reason,
    }
    return await db.update("templates", template_id, changes)


async def _get(db: Db, template_id: str) -> Row:
    rows = await db.select("templates", id=f"eq.{template_id}")
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "template not found")
    return rows[0]
