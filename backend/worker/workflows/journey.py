"""JourneyWorkflow: one deterministic interpreter for every journey definition (guide 4.2)."""

from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

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


@dataclass(frozen=True)
class JourneyRunInput:
    run_id: str
    journey_id: str
    journey_version_id: str
    contact_id: str
    definition: dict[str, Any]  # journey_versions.definition, pinned for this run


@workflow.defn
class JourneyWorkflow:
    def __init__(self) -> None:
        self._current = ""
        self._waiting = ""

    @workflow.query
    def current_state(self) -> dict[str, str]:
        """For the panel: where the run is and what it waits for."""
        return {"node_id": self._current, "waiting": self._waiting}

    @workflow.run
    async def run(self, run: JourneyRunInput) -> str:
        definition = JourneyDefinition.model_validate(run.definition)
        nodes = {node.id: node for node in definition.nodes}
        next_of = {edge.from_: edge.to for edge in definition.edges if edge.port is None}
        contact = await workflow.execute_activity_method(
            JourneyActivities.load_contact, run.contact_id, start_to_close_timeout=ACTIVITY_TIMEOUT
        )
        context: dict[str, Any] = {"contact": asdict(contact)}
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
                    str(resolve(path, context) or "")
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
                await workflow.sleep(node.duration)
                self._waiting = ""
                current = next_of[current]
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
                context["contact"] = asdict(contact)
                current = next_of[current]
            elif isinstance(node, BranchNode):
                matched = (c.next for c in node.conditions if condition_matches(c.if_, context))
                current = next(matched, node.else_)
            elif isinstance(node, WaitForReplyNode):
                raise ApplicationError(
                    "wait_for_reply arrives with the signals step", non_retryable=True
                )
            else:
                current = next_of[current]

    async def _finish(self, run: JourneyRunInput, node_id: str, status: str) -> str:
        await workflow.execute_activity_method(
            JourneyActivities.record_run_progress,
            RunProgress(run.run_id, node_id, status=status),
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )
        return status
