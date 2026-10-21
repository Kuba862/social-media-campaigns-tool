"""Connector registry: sync_connectors.name picks the module, the row's config configures it."""

from collections.abc import Callable, Mapping
from typing import Any

from sync.connectors.fake import FakeConnector
from sync.framework import Connector


def _fake(config: Mapping[str, Any]) -> Connector:
    return FakeConnector(
        default_region=config.get("default_region", "PL"), fail=bool(config.get("fail", False))
    )


BUILDERS: dict[str, Callable[[Mapping[str, Any]], Connector]] = {"fake": _fake}


def build(name: str, config: Mapping[str, Any]) -> Connector:
    try:
        builder = BUILDERS[name]
    except KeyError:
        raise KeyError(f"unknown connector {name}") from None
    return builder(config)
