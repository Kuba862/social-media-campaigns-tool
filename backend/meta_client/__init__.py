"""Anti-corruption layer for the WhatsApp Cloud API. Nothing outside this package sees Meta JSON."""

from meta_client.client import MetaClient
from meta_client.errors import MetaError, MetaPermanentError, MetaTransientError
from meta_client.models import (
    Button,
    CreatedTemplate,
    QuickReplyButton,
    SendResult,
    ServiceMessageSpec,
    TemplateSpec,
    TemplateState,
    UrlButton,
)
from meta_client.webhooks import (
    InboundMessageEvent,
    MessageStatusEvent,
    TemplateStatusEvent,
    WebhookEvent,
    parse_webhook,
    signature_is_valid,
)

__all__ = [
    "Button",
    "CreatedTemplate",
    "InboundMessageEvent",
    "MessageStatusEvent",
    "MetaClient",
    "MetaError",
    "MetaPermanentError",
    "MetaTransientError",
    "QuickReplyButton",
    "SendResult",
    "ServiceMessageSpec",
    "TemplateSpec",
    "TemplateState",
    "TemplateStatusEvent",
    "UrlButton",
    "WebhookEvent",
    "parse_webhook",
    "signature_is_valid",
]
