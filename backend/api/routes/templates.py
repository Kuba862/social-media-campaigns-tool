"""Templates: drafts live in our table, submit sends them to Meta, sync pulls Meta's verdict."""

from fastapi import APIRouter, Depends, HTTPException, Response, status

from api.auth import current_user
from api.db import Row
from api.deps import AppSettings, Db, Meta, OptionalMeta
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
            "components": _components(spec),
            "status": "DRAFT",
        },
    )


def _components(spec: TemplateSpec) -> dict[str, object]:
    """What we store: Meta's parts plus the variable names, legacy quick replies as buttons."""
    stored = spec.model_dump(include={"header", "body", "footer", "example_values"})
    stored["buttons"] = [button.model_dump() for button in spec.all_buttons]
    stored["variables"] = spec.variables
    return stored


def _spec(row: Row) -> TemplateSpec:
    """A stored row back as a spec; `variables` is derived, so it is not a field."""
    components = {k: v for k, v in row["components"].items() if k != "variables"}
    return TemplateSpec(
        name=row["name"], language=row["language"], category=row["category"], **components
    )


@router.post("/{template_id}/submit")
async def submit_template(template_id: str, db: Db, meta: Meta) -> Row:
    row = await _get(db, template_id)
    if row["status"] != "DRAFT":
        raise HTTPException(status.HTTP_409_CONFLICT, f"template is {row['status']}, not DRAFT")
    try:
        created = await meta.create_template(_spec(row))
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


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(template_id: str, db: Db, meta: OptionalMeta) -> Response:
    """Removes the row; a template Meta knows is deleted there first (its name is then blocked
    for 30 days). Messages sent with it keep their log rows with template_id set to null."""
    row = await _get(db, template_id)
    if row.get("meta_template_id") and row["status"] != "DELETED":
        if meta is None:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Meta is not configured (META_SYSTEM_USER_TOKEN)",
            )
        try:
            await meta.delete_template(row["name"], row["meta_template_id"])
        except MetaPermanentError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
        except MetaTransientError as exc:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    await db.delete("templates", template_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _get(db: Db, template_id: str) -> Row:
    rows = await db.select("templates", id=f"eq.{template_id}")
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "template not found")
    return rows[0]
