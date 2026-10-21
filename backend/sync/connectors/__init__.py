"""Connector registry: sync_connectors.name picks the module, the row's config configures it."""

from collections.abc import Callable, Mapping
from typing import Any

from sync.connectors.fake import FakeConnector
from sync.connectors.postgres import DEFAULT_COLUMNS, PostgresConnector
from sync.framework import Connector


def _fake(config: Mapping[str, Any]) -> Connector:
    return FakeConnector(
        default_region=config.get("default_region", "PL"), fail=bool(config.get("fail", False))
    )


def _postgres(config: Mapping[str, Any]) -> Connector:
    mapped = {**DEFAULT_COLUMNS, **dict(config.get("columns") or {})}
    return PostgresConnector(
        default_region=config.get("default_region"),
        table=str(config.get("table", "public.contacts_export")),
        columns={name: column for name, column in mapped.items() if column},  # null drops a field
        attributes=tuple(config.get("attributes") or ()),
        dsn_env=str(config.get("dsn_env", "SYNC_POSTGRES_DSN")),
    )


BUILDERS: dict[str, Callable[[Mapping[str, Any]], Connector]] = {
    "fake": _fake,
    "postgres": _postgres,
}


def build(name: str, config: Mapping[str, Any]) -> Connector:
    try:
        builder = BUILDERS[name]
    except KeyError:
        raise KeyError(f"unknown connector {name}") from None
    return builder(config)
