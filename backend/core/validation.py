"""Graph rules. Pure functions, no I/o."""

from collections import deque

from core.journey_schema import (
    BranchNode,
    EndNode,
    JourneyDefinition,
    SendTemplateNode,
    WaitForReplyNode
)

WAIT_TYPES = {"wait", "wait_for_reply"}


def successors(defn: JourneyDefinition) -> dict[str, list[str]]:
    """Adjacency list: edge plus branch targets (branch keeps them in the node)."""
    succ: dict[str, list[str]] = {n.id: [] for n in defn.nodes}
    for e in defn.edges:
        succ.setdefault(e.from_, []).append(e.to)
    for n in defn.nodes:
        if isinstance(n, BranchNode):
            succ[n.id] += [c.next for c in n.conditions] + [n.else_]
    return succ


def validate(defn: JourneyDefinition, approved_template_ids: set[str]) -> list[str]:
    errors: list[str] = []
    ids = [n.id for n in defn.nodes]
    if len(ids) != len(set(ids)):
        errors.append("node ids must be unique")

    starts = [n.id for n in defn.nodes if n.type == "start"]
    if len(starts) != 1:
        errors.append(f"exactly one start node required, found {len(starts)}")
    if not any(n.type == "end" for n in defn.nodes):
        errors.append("at least one end node required")

    succ = successors(defn)
    known = set(ids)
    for src, targets in succ.items():
        if src not in known:
            errors.append(f"edge from unknown node {src}")
        errors += [f"{src} points to unknown node {t}" for t in targets if t not in known]

    errors += _port_errors(defn)
    errors += [
        f"{n.id}: template {n.template_id} is not APPROVED"
        for n in defn.nodes
        if isinstance(n, SendTemplateNode) and n.template_id not in approved_template_ids
    ]

    if len(starts) == 1:
        unreachable = known - _reachable(starts[0], succ)
        if unreachable:
            errors.append(f"unreachable nodes: {sorted(unreachable)}")

    if _has_cycle_without_wait(defn, succ):
        errors.append("every cycle must pass through a wait or wait_for_reply node")
    return errors


def _port_errors(defn: JourneyDefinition) -> list[str]:
    ports: dict[str, list[str | None]] = {n.id: [] for n in defn.nodes}
    for e in defn.edges:
        if e.from_ in ports:
            ports[e.from_].append(e.port)
    errors: list[str] = []
    for n in defn.nodes:
        out = ports[n.id]
        if isinstance(n, WaitForReplyNode):
            if sorted(p or "" for p in out) != ["replied", "timeout"]:
                errors.append(f"{n.id}: needs exactly one 'replied' and one 'timeout' edge")
        elif isinstance(n, BranchNode | EndNode):
            if out:
                errors.append(f"{n.id}: {n.type} must not have edges")
        elif out != [None]:
            errors.append(f"{n.id}: needs exactly one outgoing edge without a port")
    return errors


def _reachable(start: str, succ: dict[str, list[str]]) -> set[str]:
    seen, queue = {start}, deque([start])
    while queue:
        for nxt in succ.get(queue.popleft(), []):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def _has_cycle_without_wait(defn: JourneyDefinition, succ: dict[str, list[str]]) -> bool:
    waits = {n.id for n in defn.nodes if n.type in WAIT_TYPES}
    graph = {s: [t for t in ts if t not in waits] for s, ts in succ.items() if s not in waits}
    state: dict[str, str] = {}  # missing = not visited, "open" = on the current path, "done"

    def visit(node: str) -> bool:
        state[node] = "open"
        for nxt in graph.get(node, []):
            if state.get(nxt) == "open" or (nxt not in state and visit(nxt)):
                return True
        state[node] = "done"
        return False

    return any(node not in state and visit(node) for node in graph)
    