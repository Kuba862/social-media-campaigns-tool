from collections.abc import Mapping
from typing import Any

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