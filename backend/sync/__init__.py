"""Sync connectors (guide section 5): trusted code that feeds contacts and consents from our
systems. A connector only reads and maps; the framework normalizes, writes and counts."""

from sync.framework import (
    Connector,
    ConsentChange,
    ContactUpsert,
    SyncStats,
    map_records,
    normalize_phone,
    run_sync,
    sync_batch,
)

__all__ = [
    "ConsentChange",
    "Connector",
    "ContactUpsert",
    "SyncStats",
    "map_records",
    "normalize_phone",
    "run_sync",
    "sync_batch",
]
