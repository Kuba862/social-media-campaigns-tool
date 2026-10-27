"""Dotted-path lookup and condition matching used by branch nodes."""

from typing import Any

from core.context import condition_matches, render_text, resolve

CTX: dict[str, Any] = {
    "contact": {"first_name": "Ala", "attributes": {"vip": True}},
    "reply": {"button_payload": "YES", "text": None},
}


def test_resolve_nested_path() -> None:
    assert resolve("contact.first_name", CTX) == "Ala"
    assert resolve("contact.attributes.vip", CTX) is True


def test_resolve_missing_key_returns_none() -> None:
    assert resolve("contact.last_name", CTX) is None
    assert resolve("nope", CTX) is None


def test_resolve_through_non_mapping_returns_none() -> None:
    assert resolve("contact.first_name.length", CTX) is None


def test_resolve_cannot_tell_explicit_none_from_missing() -> None:
    assert resolve("reply.text", CTX) is None


def test_condition_requires_every_pair_to_match() -> None:
    assert condition_matches({"reply.button_payload": "YES"}, CTX)
    assert condition_matches({"reply.button_payload": "YES", "contact.first_name": "Ala"}, CTX)
    assert not condition_matches({"reply.button_payload": "YES", "contact.first_name": "Ola"}, CTX)


def test_condition_on_missing_path_does_not_match() -> None:
    assert not condition_matches({"reply.missing": "x"}, CTX)


def test_empty_condition_matches_everything() -> None:
    assert condition_matches({}, CTX)


def test_render_text_fills_placeholders_and_blanks_missing_ones() -> None:
    text = "Cześć {{contact.first_name}}, {{ reply.button_payload }}!"
    assert render_text(text, CTX) == "Cześć Ala, YES!"
    assert render_text("{{contact.last_name}}x", CTX) == "x"
    assert render_text("no placeholders", CTX) == "no placeholders"
