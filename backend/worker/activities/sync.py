"""Activities of SyncConnectorWorkflow: the sync_runs row, extraction, batched writes."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from temporalio import activity
from temporalio.exceptions import ApplicationError

from storage.postgrest import Storage
from sync.connectors import build
from sync.framework import SyncStats, map_records, sync_batch


@dataclass(frozen=True)
class SyncJob:
    """One run of one connector: what every later activity needs to know."""

    connector: str
    config: dict[str, Any]
    run_id: str  # sync_runs.id
    since: str | None  # started_at of the last succeeded run, ISO 8601


@dataclass(frozen=True)
class WriteBatch:
    job: SyncJob
    records: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class FinishRun:
    run_id: str
    status: str  # succeeded | failed
    stats: dict[str, int]
    error: str | None = None


class SyncActivities:
    """Holds storage; register with Worker(activities=SyncActivities(db).all())."""

    def __init__(self, db: Storage) -> None:
        self._db = db

    def all(self) -> list[Callable[..., Any]]:
        return [self.begin_run, self.extract, self.write_batch, self.finish_run]

    @activity.defn
    async def begin_run(self, connector_name: str) -> SyncJob:
        """Open the sync_runs row and find where the previous successful run started."""
        rows = await self._db.select("sync_connectors", name=f"eq.{connector_name}")
        if not rows:
            raise ApplicationError(f"unknown connector {connector_name}", non_retryable=True)
        connector = rows[0]
        done = await self._db.select(
            "sync_runs", connector_id=f"eq.{connector['id']}", status="eq.succeeded"
        )
        since = max((str(r["started_at"]) for r in done if r.get("started_at")), default=None)
        run = await self._db.insert(
            "sync_runs",
            {
                "connector_id": connector["id"],
                "status": "running",
                "started_at": datetime.now(UTC).isoformat(),
            },
        )
        return SyncJob(connector_name, dict(connector.get("config") or {}), run["id"], since)

    @activity.defn
    async def extract(self, job: SyncJob) -> list[dict[str, Any]]:
        """Pull the source's changed records; heartbeats so a stuck source is noticed."""
        connector = build(job.connector, job.config)
        since = datetime.fromisoformat(job.since) if job.since else None
        records: list[dict[str, Any]] = []
        for record in connector.extract(since):
            records.append(dict(record))
            if len(records) % 100 == 0:
                activity.heartbeat(len(records))
        return records

    @activity.defn
    async def write_batch(self, batch: WriteBatch) -> dict[str, int]:
        connector = build(batch.job.connector, batch.job.config)
        stats = SyncStats()
        await sync_batch(
            self._db,
            map_records(connector, batch.records),
            stats,
            default_region=connector.default_region,
        )
        activity.heartbeat(len(batch.records))
        return stats.as_dict()

    @activity.defn
    async def finish_run(self, outcome: FinishRun) -> None:
        await self._db.update(
            "sync_runs",
            outcome.run_id,
            {
                "status": outcome.status,
                "stats": outcome.stats,
                "error": outcome.error,
                "ended_at": datetime.now(UTC).isoformat(),
            },
        )
