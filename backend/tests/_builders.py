"""Small helpers to build journey definitions in tests without repeating JSON."""

from typing import Any

from core.journey_schema import JourneyDefinition


def node(node_id: str, node_type: str, **fields: Any) -> dict[str, Any]:
    return {"id": node_id, "type": node_type, **fields}


def branch(node_id: str, conditions: list[dict[str, Any]], else_: str) -> dict[str, Any]:
    return {"id": node_id, "type": "branch", "conditions": conditions, "else": else_}


def edge(src: str, dst: str, port: str | None = None) -> dict[str, Any]:
    e: dict[str, Any] = {"from": src, "to": dst}
    if port is not None:
        e["port"] = port
    return e


def definition(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> JourneyDefinition:
    return JourneyDefinition.model_validate({"schema_version": 1, "nodes": nodes, "edges": edges})


START_END_NODES = [node("start", "start"), node("end", "end")]
START_END_EDGES = [edge("start", "end")]
