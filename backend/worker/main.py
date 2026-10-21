"""Temporal worker: connects, registers workflows and activities, serves task queue wa-journeys."""

import asyncio
import logging

import httpx
from temporalio.client import Client
from temporalio.worker import Worker

from meta_client import MetaClient
from storage.postgrest import PostgrestClient
from worker.activities.hello import say_hello
from worker.activities.journey import JourneyActivities
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
    http = httpx.AsyncClient(timeout=10.0)
    db = PostgrestClient(
        http,
        supabase_url=settings.supabase_url,
        service_role_key=settings.supabase_service_role_key,
    )
    meta = (
        MetaClient(
            http,
            graph_version=settings.meta_graph_version,
            waba_id=settings.meta_waba_id,
            phone_number_id=settings.meta_phone_number_id,
            access_token=settings.meta_system_user_token,
        )
        if settings.meta_system_user_token
        else None
    )
    journey = JourneyActivities(
        db, meta, send_mode=settings.wa_send_mode, allowlist=settings.wa_allowed_test_recipients
    )
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[HelloWorkflow],
        activities=[say_hello, *journey.all()],
    )
    logging.info("worker ready on %s, task queue %s", settings.temporal_address, TASK_QUEUE)
    try:
        await worker.run()
    finally:
        await http.aclose()


if __name__ == "__main__":
    asyncio.run(main())
