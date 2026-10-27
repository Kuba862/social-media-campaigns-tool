"""Pure functions between our models and Meta payloads. Meta's shapes stay in this package."""

from typing import Any

from meta_client.models import CreatedTemplate, SendResult, TemplateSpec, TemplateState


def template_create_payload(spec: TemplateSpec) -> dict[str, Any]:
    body: dict[str, Any] = {"type": "BODY", "text": spec.body}
    if spec.example_values:
        body["example"] = {"body_text": [spec.example_values]}
    components: list[dict[str, Any]] = [body]
    if spec.quick_replies:
        components.append(
            {
                "type": "BUTTONS",
                "buttons": [{"type": "QUICK_REPLY", "text": text} for text in spec.quick_replies],
            }
        )
    return {
        "name": spec.name,
        "language": spec.language,
        "category": spec.category,
        "parameter_format": "positional",
        "components": components,
    }


def message_payload(
    to_e164: str, template_name: str, language: str, body_values: list[str]
) -> dict[str, Any]:
    template: dict[str, Any] = {"name": template_name, "language": {"code": language}}
    if body_values:
        template["components"] = [
            {"type": "body", "parameters": [{"type": "text", "text": v} for v in body_values]}
        ]
    return {
        "messaging_product": "whatsapp",
        "to": to_e164.lstrip("+"),
        "type": "template",
        "template": template,
    }


def text_message_payload(to_e164: str, text: str) -> dict[str, Any]:
    """A free-form (service) message; Meta accepts it only inside the 24-hour window."""
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_e164.lstrip("+"),
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }


def parse_created_template(data: dict[str, Any]) -> CreatedTemplate:
    return CreatedTemplate(meta_template_id=str(data["id"]), status=data["status"])


def parse_template_state(item: dict[str, Any]) -> TemplateState:
    reason = item.get("rejected_reason")
    return TemplateState(
        meta_template_id=str(item["id"]),
        status=item["status"],
        rejection_reason=None if reason in (None, "NONE") else str(reason),
    )


def parse_send_result(data: dict[str, Any]) -> SendResult:
    message = data["messages"][0]
    status = str(message.get("message_status", "accepted"))
    return SendResult(wamid=str(message["id"]), status=status)
