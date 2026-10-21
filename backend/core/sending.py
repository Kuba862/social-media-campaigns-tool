"""Who may receive a message. Pure rules shared by the API's test send and the worker's activity."""

from collections.abc import Iterable


def parse_allowlist(value: str) -> frozenset[str]:
    """Comma-separated E.164 numbers from the environment, blanks ignored."""
    return frozenset(item.strip() for item in value.split(",") if item.strip())


def recipient_allowed(to_e164: str, send_mode: str, allowlist: Iterable[str]) -> bool:
    """In test mode only allow-listed numbers; live mode (never set in the PoC) allows everyone."""
    if send_mode == "live":
        return True
    return to_e164 in set(allowlist)
