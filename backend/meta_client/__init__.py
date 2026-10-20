"""Anti-corruption layer for the WhatsApp Cloud API. Nothing outside this package sees Meta JSON."""

from meta_client.client import MetaClient
from meta_client.errors import MetaError, MetaPermanentError, MetaTransientError
from meta_client.models import CreatedTemplate, SendResult, TemplateSpec, TemplateState

__all__ = [
    "CreatedTemplate",
    "MetaClient",
    "MetaError",
    "MetaPermanentError",
    "MetaTransientError",
    "SendResult",
    "TemplateSpec",
    "TemplateState",
]
