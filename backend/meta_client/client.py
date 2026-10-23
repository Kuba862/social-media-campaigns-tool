"""Thin async client for the WhatsApp Cloud API. One method per operation the PoC needs."""

from typing import Any

import httpx

from meta_client.errors import THROTTLING_CODES, MetaError, MetaPermanentError, MetaTransientError
from meta_client.mapping import (
    message_payload,
    parse_created_template,
    parse_send_result,
    parse_template_state,
    template_create_payload,
)
from meta_client.models import CreatedTemplate, SendResult, TemplateSpec, TemplateState

TEMPLATE_FIELDS = "id,name,language,status,category,rejected_reason"


class MetaClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        graph_version: str,
        waba_id: str,
        phone_number_id: str,
        access_token: str,
    ) -> None:
        self._http = http
        self._base = f"https://graph.facebook.com/{graph_version}"
        self._waba_id = waba_id
        self._phone_number_id = phone_number_id
        self._headers = {"Authorization": f"Bearer {access_token}"}

    async def create_template(self, spec: TemplateSpec) -> CreatedTemplate:
        payload = template_create_payload(spec)
        data = await self._post(f"/{self._waba_id}/message_templates", payload)
        return parse_created_template(data)

    async def get_template_state(self, name: str, language: str) -> TemplateState | None:
        """None when Meta has no template with this name and language."""
        data = await self._get(
            f"/{self._waba_id}/message_templates",
            {"name": name, "language": language, "fields": TEMPLATE_FIELDS},
        )
        items = [item for item in data.get("data", []) if item.get("language") == language]
        return parse_template_state(items[0]) if items else None

    async def send_template(
        self, to_e164: str, template_name: str, language: str, body_values: list[str]
    ) -> SendResult:
        payload = message_payload(to_e164, template_name, language, body_values)
        data = await self._post(f"/{self._phone_number_id}/messages", payload)
        return parse_send_result(data)

    async def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        return await self._request("GET", path, params=params)

    async def _post(self, path: str, json: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", path, json=json)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = await self._http.request(
                method, self._base + path, params=params, json=json, headers=self._headers
            )
        except httpx.HTTPError as exc:
            raise MetaTransientError(f"network error calling Meta: {exc}") from exc
        if response.is_success:
            body: dict[str, Any] = response.json()
            return body
        raise _error_from(response)


def _error_from(response: httpx.Response) -> MetaError:
    try:
        error: dict[str, Any] = response.json().get("error", {})
    except ValueError:
        error = {}
    code = error.get("code")
    message = f"Meta {response.status_code}: {error.get('message') or response.text[:200]}"
    # Code 100 ("Invalid parameter") says nothing by itself; the reason sits in these two fields.
    details_text = (error.get("error_data") or {}).get("details")
    reasons = [str(r) for r in (error.get("error_user_msg"), details_text) if r]
    if reasons:
        message = f"{message} ({'; '.join(reasons)})"
    details: dict[str, Any] = {
        "http_status": response.status_code,
        "code": code,
        "subcode": error.get("error_subcode"),
        "fbtrace_id": error.get("fbtrace_id"),
    }
    if response.status_code >= 500 or code in THROTTLING_CODES:
        return MetaTransientError(message, **details)
    return MetaPermanentError(message, **details)
