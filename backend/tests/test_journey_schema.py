"""JourneyDefinition parses the guide's JSON format and rejects anything else."""

from datetime import timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from core.journey_schema import JourneyDefinition, SendTextNode, WaitForReplyNode, WaitNode
from tests._builders import START_END_EDGES, START_END_NODES, definition, edge, node


def test_guide_example_parses(guide_example: JourneyDefinition) -> None:
    assert [n.type for n in guide_example.nodes] == [
        "start",
        "send_template",
        "wait",
        "wait_for_reply",
        "branch",
        "update_contact",
        "end",
    ]
    assert len(guide_example.edges) == 6


def test_iso_8601_durations_become_timedelta(guide_example: JourneyDefinition) -> None:
    wait, reply = guide_example.nodes[2], guide_example.nodes[3]
    assert isinstance(wait, WaitNode)
    assert wait.duration == timedelta(days=2)
    assert isinstance(reply, WaitForReplyNode)
    assert reply.timeout == timedelta(hours=24)


def test_reserved_word_aliases_round_trip(
    guide_example_json: dict[str, Any], guide_example: JourneyDefinition
) -> None:
    """`if`, `else` and `from` are Python keywords; they must still appear as such in JSON."""
    dumped = guide_example.model_dump(by_alias=True, mode="json")
    assert dumped["edges"][0]["from"] == "start"
    branch = dumped["nodes"][4]
    assert set(branch) == {"id", "type", "conditions", "else"}
    assert branch["conditions"][0]["if"] == {"reply.button_payload": "YES"}
    assert JourneyDefinition.model_validate(dumped) == guide_example


def test_wait_for_reply_uses_timeout_not_duration() -> None:
    nodes = [
        node("start", "start"),
        node("w", "wait_for_reply", duration="PT1H"),
        node("end", "end"),
    ]
    with pytest.raises(ValidationError, match="timeout"):
        definition(nodes, [])


def test_unknown_node_type_rejected() -> None:
    nodes = [node("start", "start"), node("x", "teleport"), node("end", "end")]
    with pytest.raises(ValidationError, match="type"):
        definition(nodes, START_END_EDGES)


def test_extra_fields_rejected() -> None:
    nodes = [node("start", "start", colour="red"), node("end", "end")]
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        definition(nodes, START_END_EDGES)


def test_edge_port_must_be_replied_or_timeout() -> None:
    with pytest.raises(ValidationError, match="port"):
        definition(START_END_NODES, [edge("start", "end", port="maybe")])


def test_schema_version_must_be_1() -> None:
    raw = {"schema_version": 2, "nodes": START_END_NODES, "edges": START_END_EDGES}
    with pytest.raises(ValidationError, match="schema_version"):
        JourneyDefinition.model_validate(raw)


def test_node_count_limits() -> None:
    with pytest.raises(ValidationError, match="at least 1"):
        definition([], [])
    too_many = [node("start", "start")] + [node(f"n{i}", "end") for i in range(50)]
    with pytest.raises(ValidationError, match="at most 50"):
        definition(too_many, [])


def test_models_are_immutable(guide_example: JourneyDefinition) -> None:
    with pytest.raises(ValidationError, match="frozen"):
        guide_example.nodes[0].id = "other"  # type: ignore[misc]


def _text_journey(text: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "nodes": [
            {"id": "start", "type": "start"},
            {"id": "hi", "type": "send_text", "text": text},
            {"id": "end", "type": "end"},
        ],
        "edges": [{"from": "start", "to": "hi"}, {"from": "hi", "to": "end"}],
    }


def test_send_text_node_parses_with_skip_as_the_default_policy() -> None:
    hi = JourneyDefinition.model_validate(_text_journey("Cześć {{contact.first_name}}")).nodes[1]
    assert isinstance(hi, SendTextNode) and hi.if_closed == "skip"
    with pytest.raises(ValidationError):
        JourneyDefinition.model_validate(_text_journey(""))
