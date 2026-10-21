"""Pure sending rules from core: the recipient guard and the consent rule."""

from core.consent import has_active_consent
from core.sending import parse_allowlist, recipient_allowed

ALLOWED = parse_allowlist(" +48600000001, +48600000002 ,,")


def test_allowlist_parsing_trims_and_drops_blanks() -> None:
    assert ALLOWED == frozenset({"+48600000001", "+48600000002"})
    assert parse_allowlist("") == frozenset()


def test_test_mode_allows_listed_numbers_only() -> None:
    assert recipient_allowed("+48600000001", "test", ALLOWED)
    assert not recipient_allowed("+48600000009", "test", ALLOWED)
    assert not recipient_allowed("+48600000001", "test", frozenset())


def test_live_mode_allows_everyone() -> None:
    assert recipient_allowed("+48600000009", "live", frozenset())


def test_latest_consent_wins_regardless_of_order() -> None:
    opted_in = {"status": "opted_in", "captured_at": "2026-10-01T10:00:00+00:00"}
    opted_out = {"status": "opted_out", "captured_at": "2026-10-05T10:00:00+00:00"}
    assert has_active_consent([opted_in])
    assert not has_active_consent([opted_in, opted_out])
    assert not has_active_consent([opted_out, opted_in])
    assert not has_active_consent([])
    assert not has_active_consent([{**opted_in, "channel": "sms"}])
