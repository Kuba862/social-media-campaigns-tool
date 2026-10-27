"""Pure functions between our models and Meta payloads. Meta's shapes stay in this package."""

from typing import Any

from meta_client.models import CreatedTemplate, SendResult, TemplateSpec, TemplateState


def template_create_payload(spec: TemplateSpec, header_handle: str | None = None) -> dict[str, Any]:
    """Meta's components in their order: HEADER, BODY (positional variables), FOOTER, BUTTONS.
    An image header needs the handle of a sample uploaded through the Resumable Upload API."""
    components: list[dict[str, Any]] = []
    if spec.header:
        components.append({"type": "HEADER", "format": "TEXT", "text": spec.header})
    elif spec.header_image_url:
        if not header_handle:
            raise ValueError("an image header needs the uploaded sample's handle")
        components.append(
            {"type": "HEADER", "format": "IMAGE", "example": {"header_handle": [header_handle]}}
        )
    body: dict[str, Any] = {"type": "BODY", "text": spec.positional_body}
    if spec.example_values:
        body["example"] = {"body_text": [spec.example_values]}
    components.append(body)
    if spec.footer:
        components.append({"type": "FOOTER", "text": spec.footer})
    buttons = [
        {"type": "QUICK_REPLY", "text": button.text}
        if button.type == "quick_reply"
        else {"type": "URL", "text": button.text, "url": button.url}
        for button in spec.all_buttons
    ]
    if buttons:
        components.append({"type": "BUTTONS", "buttons": buttons})
    return {
        "name": spec.name,
        "language": spec.language,
        "category": spec.category,
        "parameter_format": "positional",
        "components": components,
    }


def message_payload(
    to_e164: str,
    template_name: str,
    language: str,
    body_values: list[str],
    header_image_url: str | None = None,
) -> dict[str, Any]:
    template: dict[str, Any] = {"name": template_name, "language": {"code": language}}
    components: list[dict[str, Any]] = []
    if header_image_url:
        components.append(
            {
                "type": "header",
                "parameters": [{"type": "image", "image": {"link": header_image_url}}],
            }
        )
    if body_values:
        components.append(
            {"type": "body", "parameters": [{"type": "text", "text": v} for v in body_values]}
        )
    if components:
        template["components"] = components
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


def image_message_payload(to_e164: str, link: str, caption: str | None = None) -> dict[str, Any]:
    """A free-form image message (with an optional caption); the 24-hour window applies."""
    image: dict[str, Any] = {"link": link}
    if caption:
        image["caption"] = caption
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_e164.lstrip("+"),
        "type": "image",
        "image": image,
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
    return SendResult(wamid=str(message["id"]), status=status, raw=data)
