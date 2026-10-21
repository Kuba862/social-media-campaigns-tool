"""SyncConnectorWorkflow: one run of one connector, from a Temporal Schedule or on demand."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from worker.activities.sync import FinishRun, SyncActivities, SyncJob, WriteBatch

BATCH_SIZE = 100
ROW_TIMEOUT = timedelta(seconds=30)
EXTRACT_TIMEOUT = timedelta(minutes=30)
WRITE_TIMEOUT = timedelta(minutes=5)
HEARTBEAT = timedelta(minutes=2)
RETRY = RetryPolicy(initial_interval=timedelta(seconds=5), maximum_attempts=3)


@workflow.defn
class SyncConnectorWorkflow:
    @workflow.run
    async def run(self, connector: str) -> dict[str, int]:
        """begin_run, extract, write in batches, finish_run; the row records success or failure."""
        job: SyncJob = await workflow.execute_activity_method(
            SyncActivities.begin_run, connector, start_to_close_timeout=ROW_TIMEOUT
        )
        stats: dict[str, int] = {}
        try:
            records = await workflow.execute_activity_method(
                SyncActivities.extract,
                job,
                start_to_close_timeout=EXTRACT_TIMEOUT,
                heartbeat_timeout=HEARTBEAT,
                retry_policy=RETRY,
            )
            stats["extracted"] = len(records)
            for start in range(0, len(records), BATCH_SIZE):
                part = await workflow.execute_activity_method(
                    SyncActivities.write_batch,
                    WriteBatch(job, records[start : start + BATCH_SIZE]),
                    start_to_close_timeout=WRITE_TIMEOUT,
                    heartbeat_timeout=HEARTBEAT,
                    retry_policy=RETRY,
                )
                for key, value in part.items():
                    stats[key] = stats.get(key, 0) + value
        except ActivityError as exc:
            await self._finish(job, "failed", stats, str(exc.cause or exc))
            raise
        await self._finish(job, "succeeded", stats, None)
        return stats

    async def _finish(
        self, job: SyncJob, status: str, stats: dict[str, int], error: str | None
    ) -> None:
        await workflow.execute_activity_method(
            SyncActivities.finish_run,
            FinishRun(job.run_id, status, stats, error),
            start_to_close_timeout=ROW_TIMEOUT,
        )
