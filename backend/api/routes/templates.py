"""Templates: drafts live in our table, submit sends them to Meta, sync pulls Meta's verdict."""

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, status

from api.auth import current_user
from api.db import Row
from api.deps import AppSettings, Db, Http, Meta, OptionalMeta
from meta_client import MetaPermanentError, MetaTransientError, ServiceMessageSpec, TemplateSpec

router = APIRouter(prefix="/templates", tags=["templates"], dependencies=[Depends(current_user)])

IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # Meta's limit for image headers


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
            "kind": "template",
            "components": _components(spec),
            "status": "DRAFT",
        },
    )


@router.post("/service", status_code=status.HTTP_201_CREATED)
async def create_service_message(spec: ServiceMessageSpec, db: Db, settings: AppSettings) -> Row:
    """A saved service message: ready at once, never sent to Meta for review."""
    return await db.insert(
        "templates",
        {
            "waba_id": settings.meta_waba_id,
            "name": spec.name,
            "language": spec.language,
            "category": "SERVICE",
            "kind": "service",
            "components": {"body": spec.body, "image_url": spec.image_url, "variables": []},
            "status": "READY",
        },
    )


async def _download_image(http: httpx.AsyncClient, url: str) -> tuple[bytes, str]:
    """The sample for Meta: a JPEG or PNG of at most 5 MB from an https address."""
    try:
        response = await http.get(url, follow_redirects=True, timeout=15.0)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"could not download the header image: {exc}"
        ) from exc
    mime = response.headers.get("content-type", "").split(";")[0].strip().lower()
    if not response.is_success or mime not in IMAGE_TYPES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"the header image must be a JPEG or PNG over https (got {mime or 'nothing'})",
        )
    if len(response.content) > MAX_IMAGE_BYTES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "the header image exceeds 5 MB")
    return response.content, mime


def _components(spec: TemplateSpec) -> dict[str, object]:
    """What we store: Meta's parts plus the variable names, legacy quick replies as buttons."""
    stored = spec.model_dump(
        include={"header", "header_image_url", "body", "footer", "example_values"}
    )
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
async def submit_template(template_id: str, db: Db, meta: Meta, http: Http) -> Row:
    """An image header first goes to Meta as a sample (download, then Resumable Upload)."""
    row = await _get(db, template_id)
    _meta_kind(row)
    if row["status"] != "DRAFT":
        raise HTTPException(status.HTTP_409_CONFLICT, f"template is {row['status']}, not DRAFT")
    spec = _spec(row)
    try:
        handle = None
        if spec.header_image_url:
            data, mime = await _download_image(http, spec.header_image_url)
            handle = await meta.upload_sample(data, mime, f"{spec.name}.{IMAGE_TYPES[mime]}")
        created = await meta.create_template(spec, header_handle=handle)
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
    _meta_kind(row)
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


def _meta_kind(row: Row) -> None:
    if row.get("kind", "template") != "template":
        raise HTTPException(status.HTTP_409_CONFLICT, "service messages are not submitted to Meta")


async def _get(db: Db, template_id: str) -> Row:
    rows = await db.select("templates", id=f"eq.{template_id}")
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "template not found")
    return rows[0]
