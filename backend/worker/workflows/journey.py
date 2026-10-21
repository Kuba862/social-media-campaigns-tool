"""JourneyWorkflow: one deterministic interpreter for every journey definition (guide 4.2)."""

from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Any, Literal

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from core.context import condition_matches, resolve
    from core.journey_schema import (
        BranchNode,
        EndNode,
        JourneyDefinition,
        SendTemplateNode,
        StartNode,
        UpdateContactNode,
        WaitForReplyNode,
        WaitNode,
    )
    from worker.activities.journey import JourneyActivities, RunProgress, SendTemplateInput

ACTIVITY_TIMEOUT = timedelta(seconds=30)
SEND_RETRY = RetryPolicy(initial_interval=timedelta(seconds=2), maximum_attempts=5)
TASK_QUEUE = "wa-journeys"


@dataclass(frozen=True)
class JourneyRunInput:
    run_id: str
    journey_id: str
    journey_version_id: str
    contact_id: str
    definition: dict[str, Any]  # journey_versions.definition, pinned for this run


@dataclass(frozen=True)
class ReplySignal:
    """An inbound message routed to this run by the webhook; `reply.*` in branch conditions."""

    wamid: str
    text: str | None = None
    button_payload: str | None = None
    context_wamid: str | None = None


@workflow.defn
class JourneyWorkflow:
    def __init__(self) -> None:
        self._current = ""
        self._waiting = ""
        self._context: dict[str, Any] = {}
        self._reply: ReplySignal | None = None  # pending until the next wait_for_reply consumes it
        self._opted_out = False
        self._statuses: list[dict[str, Any]] = []

    @workflow.signal
    def inbound_message(self, reply: ReplySignal) -> None:
        self._reply = reply  # a newer reply replaces an unconsumed one

    @workflow.signal
    def opt_out(self) -> None:
        self._opted_out = True

    @workflow.signal
    def message_status(self, status: dict[str, Any]) -> None:
        """Delivery statuses for this run's messages; kept for future nodes, bounded in size."""
        self._statuses = [*self._statuses[-49:], status]

    @workflow.query
    def current_state(self) -> dict[str, str]:
        """For the panel: where the run is and what it waits for."""
        return {"node_id": self._current, "waiting": self._waiting}

    @workflow.run
    async def run(self, run: JourneyRunInput) -> str:
        definition = JourneyDefinition.model_validate(run.definition)
        nodes = {node.id: node for node in definition.nodes}
        next_of = {edge.from_: edge.to for edge in definition.edges if edge.port is None}
        ports = {(edge.from_, edge.port): edge.to for edge in definition.edges if edge.port}
        contact = await workflow.execute_activity_method(
            JourneyActivities.load_contact, run.contact_id, start_to_close_timeout=ACTIVITY_TIMEOUT
        )
        self._context = {"contact": asdict(contact)}
        current = next(node.id for node in definition.nodes if isinstance(node, StartNode))
        visits: dict[str, int] = {}

        while True:
            self._current = current
            node = nodes[current]
            visits[current] = visits.get(current, 0) + 1
            await workflow.execute_activity_method(
                JourneyActivities.record_run_progress,
                RunProgress(run.run_id, current),
                start_to_close_timeout=ACTIVITY_TIMEOUT,
            )
            if self._opted_out:
                return await self._finish(run, current, "opted_out")
            if isinstance(node, EndNode):
                return await self._finish(run, current, "completed")
            if isinstance(node, SendTemplateNode):
                consent = await workflow.execute_activity_method(
                    JourneyActivities.check_consent,
                    run.contact_id,
                    start_to_close_timeout=ACTIVITY_TIMEOUT,
                )
                if not consent:
                    return await self._finish(run, current, "skipped_no_consent")
                values = [
                    str(resolve(path, self._context) or "")
                    for _, path in sorted(node.variables.items(), key=lambda kv: int(kv[0]))
                ]
                request = SendTemplateInput(
                    run.run_id,
                    workflow.info().workflow_id,
                    current,
                    visits[current],
                    run.contact_id,
                    node.template_id,
                    values,
                )
                result = await workflow.execute_activity_method(
                    JourneyActivities.send_template,
                    request,
                    start_to_close_timeout=ACTIVITY_TIMEOUT,
                    retry_policy=SEND_RETRY,
                )
                if result.status == "failed":
                    return await self._finish(run, current, "failed")
                current = next_of[current]
            elif isinstance(node, WaitNode):
                self._waiting = "sleep"
                await self._pause(node.duration)
                self._waiting = ""
                if self._opted_out:
                    return await self._finish(run, current, "opted_out")
                current = next_of[current]
            elif isinstance(node, WaitForReplyNode):
                self._waiting = "reply"
                port = await self._await_reply(node.timeout)
                self._waiting = ""
                if port is None:
                    return await self._finish(run, current, "opted_out")
                current = ports[(current, port)]
            elif isinstance(node, UpdateContactNode):
                await workflow.execute_activity_method(
                    JourneyActivities.update_contact,
                    args=[run.contact_id, node.set],
                    start_to_close_timeout=ACTIVITY_TIMEOUT,
                )
                contact = await workflow.execute_activity_method(
                    JourneyActivities.load_contact,
                    run.contact_id,
                    start_to_close_timeout=ACTIVITY_TIMEOUT,
                )
                self._context["contact"] = asdict(contact)
                current = next_of[current]
            elif isinstance(node, BranchNode):
                matched = (
                    c.next for c in node.conditions if condition_matches(c.if_, self._context)
                )
                current = next(matched, node.else_)
            else:
                current = next_of[current]

    async def _pause(self, duration: timedelta) -> None:
        """A wait that opt_out can cut short; the timer firing is the normal way out."""
        try:
            await workflow.wait_condition(lambda: self._opted_out, timeout=duration)
        except TimeoutError:
            pass

    async def _await_reply(self, timeout: timedelta) -> Literal["replied", "timeout"] | None:
        """Port to follow: "replied", "timeout", or None when opt_out arrived instead."""
        try:
            await workflow.wait_condition(
                lambda: self._reply is not None or self._opted_out, timeout=timeout
            )
        except TimeoutError:
            self._context.pop("reply", None)
            return "timeout"
        if self._opted_out:
            return None
        self._context["reply"] = asdict(self._reply) if self._reply else {}
        self._reply = None
        return "replied"

    async def _finish(self, run: JourneyRunInput, node_id: str, status: str) -> str:
        await workflow.execute_activity_method(
            JourneyActivities.record_run_progress,
            RunProgress(run.run_id, node_id, status=status),
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )
        return status
