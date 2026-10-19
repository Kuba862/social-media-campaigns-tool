"""Temporal worker: connects, registers workflows and activities, serves task queue wa-journeys."""

import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from worker.activities.hello import say_hello
from worker.settings import load_settings
from worker.workflows.hello import HelloWorkflow

TASK_QUEUE = "wa-journeys"


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = load_settings()
    client = await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
        api_key=settings.temporal_api_key or None,
        tls=bool(settings.temporal_api_key),
    )
    worker = Worker(
        client, task_queue=TASK_QUEUE, workflows=[HelloWorkflow], activities=[say_hello]
    )
    logging.info("worker ready on %s, task queue %s", settings.temporal_address, TASK_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
