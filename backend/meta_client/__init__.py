"""Anti-corruption layer for the WhatsApp Cloud API. Nothing outside this package sees Meta JSON."""

from meta_client.client import MetaClient
from meta_client.errors import MetaError, MetaPermanentError, MetaTransientError
from meta_client.models import CreatedTemplate, SendResult, TemplateSpec, TemplateState
from meta_client.webhooks import (
    InboundMessageEvent,
    MessageStatusEvent,
    TemplateStatusEvent,
    WebhookEvent,
    parse_webhook,
    signature_is_valid,
)

__all__ = [
    "CreatedTemplate",
    "InboundMessageEvent",
    "MessageStatusEvent",
    "MetaClient",
    "MetaError",
    "MetaPermanentError",
    "MetaTransientError",
    "SendResult",
    "TemplateSpec",
    "TemplateState",
    "TemplateStatusEvent",
    "WebhookEvent",
    "parse_webhook",
    "signature_is_valid",
]
