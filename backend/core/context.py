"""Dotted-path lookup used by branch conditions, template variables and text nodes. No I/O."""

import re
from collections.abc import Mapping
from typing import Any

PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_.]+)\s*\}\}")


def resolve(path: str, ctx: Mapping[str, Any]) -> Any:
    """'contact.first_name' -> ctx['contact']['first_name']; missing -> None."""
    current: Any = ctx
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def condition_matches(condition: Mapping[str, str], ctx: Mapping[str, Any]) -> bool:
    return all(resolve(path, ctx) == expected for path, expected in condition.items())


def render_text(text: str, ctx: Mapping[str, Any]) -> str:
    """'Cześć {{contact.first_name}}' with the context's values; a missing path renders as ''."""

    def value(match: re.Match[str]) -> str:
        found = resolve(match.group(1), ctx)
        return "" if found is None else str(found)

    return PLACEHOLDER.sub(value, text)
