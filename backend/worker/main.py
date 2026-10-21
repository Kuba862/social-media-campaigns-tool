"""Temporal worker: connects, registers workflows and activities, serves task queue wa-journeys."""

import asyncio
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import httpx
from temporalio.client import Client
from temporalio.worker import Worker

from meta_client import MetaClient
from storage.postgrest import PostgrestClient
from worker.activities.hello import say_hello
from worker.activities.journey import JourneyActivities
from worker.activities.sync import SyncActivities
from worker.settings import load_settings
from worker.workflows.hello import HelloWorkflow
from worker.workflows.journey import TASK_QUEUE, JourneyWorkflow
from worker.workflows.sync import SyncConnectorWorkflow


class _Health(BaseHTTPRequestHandler):
    """200 on /healthz, nothing else; for a Cloud Run *service* that must listen on $PORT."""

    def do_GET(self) -> None:
        ok = self.path == "/healthz"
        self.send_response(200 if ok else 404)
        self.end_headers()
        self.wfile.write(b"ok" if ok else b"")

    def log_message(self, format: str, *args: Any) -> None:
        return


def serve_health_if_requested() -> None:
    """Cloud Run worker pools need no port; a service does, so honour $PORT when it is set."""
    port = os.environ.get("PORT")
    if not port:
        return
    server = ThreadingHTTPServer(("", int(port)), _Health)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logging.info("health endpoint on :%s/healthz", port)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    serve_health_if_requested()
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
        workflows=[HelloWorkflow, JourneyWorkflow, SyncConnectorWorkflow],
        activities=[say_hello, *journey.all(), *SyncActivities(db).all()],
    )
    logging.info("worker ready on %s, task queue %s", settings.temporal_address, TASK_QUEUE)
    try:
        await worker.run()
    finally:
        await http.aclose()


if __name__ == "__main__":
    asyncio.run(main())
