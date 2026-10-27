"""Typed errors for the WhatsApp Cloud API. Callers decide to retry by type, never by message."""

# Graph API and WhatsApp codes that mean "slow down"; the caller retries with backoff.
THROTTLING_CODES = frozenset({4, 17, 32, 613, 80007, 130429, 131048, 131056})

# "Re-engagement message": a free-form message more than 24 hours after the customer's last one.
RE_ENGAGEMENT_CODE = 131047


class MetaError(Exception):
    """Base class. `code` is Meta's numeric code when the body carried one, else None."""

    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        code: int | None = None,
        subcode: int | None = None,
        fbtrace_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.code = code
        self.subcode = subcode
        self.fbtrace_id = fbtrace_id


class MetaTransientError(MetaError):
    """Network trouble, 5xx or throttling: the same call may succeed later."""


class MetaPermanentError(MetaError):
    """4xx with a validation, auth or policy code: retrying the same call will not help."""
