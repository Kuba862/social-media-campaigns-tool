"""Consent rules (guide section 3): the latest row per contact wins; rows are never edited."""

from collections.abc import Mapping, Sequence
from typing import Any


def has_active_consent(consents: Sequence[Mapping[str, Any]], channel: str = "whatsapp") -> bool:
    rows = [c for c in consents if c.get("channel", "whatsapp") == channel]
    if not rows:
        return False
    latest = max(rows, key=lambda c: str(c.get("captured_at", "")))
    return latest.get("status") == "opted_in"
