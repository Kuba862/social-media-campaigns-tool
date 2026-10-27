"""Graph rules from section 4.1 of the guide, one test per rule."""

from core.journey_schema import JourneyDefinition
from core.validation import validate
from tests._builders import START_END_EDGES, START_END_NODES, branch, definition, edge, node

APPROVED = {"tpl-1"}


def test_guide_example_is_valid(guide_example: JourneyDefinition) -> None:
    assert validate(guide_example, APPROVED) == []


def test_minimal_start_end_is_valid() -> None:
    assert validate(definition(START_END_NODES, START_END_EDGES), APPROVED) == []


def test_duplicate_node_ids() -> None:
    nodes = [node("start", "start"), node("end", "end"), node("end", "end")]
    assert "node ids must be unique" in validate(definition(nodes, START_END_EDGES), APPROVED)


def test_no_start_node() -> None:
    errors = validate(definition([node("end", "end")], []), APPROVED)
    assert errors == ["exactly one start node required, found 0"]


def test_two_start_nodes() -> None:
    nodes = [node("s1", "start"), node("s2", "start"), node("end", "end")]
    edges = [edge("s1", "end"), edge("s2", "end")]
    assert validate(definition(nodes, edges), APPROVED) == [
        "exactly one start node required, found 2"
    ]


def test_end_node_required() -> None:
    nodes = [node("start", "start"), node("w", "wait", duration="PT1H")]
    edges = [edge("start", "w"), edge("w", "start")]
    assert validate(definition(nodes, edges), APPROVED) == ["at least one end node required"]


def test_edge_to_unknown_node() -> None:
    errors = validate(definition(START_END_NODES, [edge("start", "ghost")]), APPROVED)
    assert "start points to unknown node ghost" in errors
    assert "unreachable nodes: ['end']" in errors


def test_edge_from_unknown_node() -> None:
    edges = [edge("start", "end"), edge("ghost", "end")]
    assert validate(definition(START_END_NODES, edges), APPROVED) == [
        "edge from unknown node ghost"
    ]


def test_branch_target_unknown() -> None:
    nodes = [
        node("start", "start"),
        branch("b", [{"if": {"reply.text": "yes"}, "next": "nowhere"}], "end"),
        node("end", "end"),
    ]
    errors = validate(definition(nodes, [edge("start", "b")]), APPROVED)
    assert errors == ["b points to unknown node nowhere"]


def test_unreachable_node_reported() -> None:
    nodes = START_END_NODES + [node("orphan", "update_contact", set={"attributes.x": 1})]
    edges = [edge("start", "end"), edge("orphan", "end")]
    assert validate(definition(nodes, edges), APPROVED) == ["unreachable nodes: ['orphan']"]


def test_wait_for_reply_needs_replied_and_timeout_edges() -> None:
    nodes = [
        node("start", "start"),
        node("w", "wait_for_reply", timeout="PT1H"),
        node("end", "end"),
    ]
    one_edge = [edge("start", "w"), edge("w", "end")]
    assert "w: needs exactly one 'replied' and one 'timeout' edge" in validate(
        definition(nodes, one_edge), APPROVED
    )
    both_ports = [edge("start", "w"), edge("w", "end", "replied"), edge("w", "end", "timeout")]
    assert validate(definition(nodes, both_ports), APPROVED) == []


def test_branch_and_end_must_not_have_outgoing_edges() -> None:
    nodes = [node("start", "start"), branch("b", [], "end"), node("end", "end")]
    edges = [edge("start", "b"), edge("b", "end"), edge("end", "start")]
    errors = validate(definition(nodes, edges), APPROVED)
    assert "b: branch must not have edges" in errors
    assert "end: end must not have edges" in errors


def test_regular_node_needs_exactly_one_unported_edge() -> None:
    nodes = [node("start", "start"), node("w", "wait", duration="PT1H"), node("end", "end")]
    message = "w: needs exactly one outgoing edge without a port"
    ported = [edge("start", "w"), edge("w", "end", "replied")]
    assert message in validate(definition(nodes, ported), APPROVED)
    doubled = [edge("start", "w"), edge("w", "end"), edge("w", "end")]
    assert message in validate(definition(nodes, doubled), APPROVED)
    no_start_edge = [edge("w", "end")]
    assert "start: needs exactly one outgoing edge without a port" in validate(
        definition(nodes, no_start_edge), APPROVED
    )


def test_send_template_requires_approved_template() -> None:
    nodes = [
        node("start", "start"),
        node("s", "send_template", template_id="tpl-9"),
        node("end", "end"),
    ]
    edges = [edge("start", "s"), edge("s", "end")]
    assert validate(definition(nodes, edges), {"tpl-1"}) == ["s: template tpl-9 is not APPROVED"]
    assert validate(definition(nodes, edges), {"tpl-9"}) == []


def test_cycle_without_wait_rejected() -> None:
    nodes = [
        node("start", "start"),
        node("a", "update_contact", set={"attributes.x": 1}),
        branch("b", [{"if": {"reply.text": "again"}, "next": "a"}], "end"),
        node("end", "end"),
    ]
    edges = [edge("start", "a"), edge("a", "b")]
    assert validate(definition(nodes, edges), APPROVED) == [
        "every cycle must pass through a wait or wait_for_reply node"
    ]


def test_cycle_through_wait_allowed() -> None:
    nodes = [
        node("start", "start"),
        node("a", "update_contact", set={"attributes.x": 1}),
        node("w", "wait", duration="PT1H"),
        branch("b", [{"if": {"reply.text": "again"}, "next": "a"}], "end"),
        node("end", "end"),
    ]
    edges = [edge("start", "a"), edge("a", "w"), edge("w", "b")]
    assert validate(definition(nodes, edges), APPROVED) == []


def test_cycle_through_wait_for_reply_allowed() -> None:
    nodes = [
        node("start", "start"),
        node("a", "update_contact", set={"attributes.x": 1}),
        node("w", "wait_for_reply", timeout="PT1H"),
        branch("b", [{"if": {"reply.text": "again"}, "next": "a"}], "end"),
        node("end", "end"),
    ]
    edges = [
        edge("start", "a"),
        edge("a", "w"),
        edge("w", "b", "replied"),
        edge("w", "end", "timeout"),
    ]
    assert validate(definition(nodes, edges), APPROVED) == []


def test_saved_service_messages_must_exist_when_the_caller_lists_them() -> None:
    nodes = [node("start", "start"), node("t", "send_text", message_id="svc-1"), node("end", "end")]
    edges = [edge("start", "t"), edge("t", "end")]
    assert validate(definition(nodes, edges), APPROVED) == []  # the list is optional
    assert validate(definition(nodes, edges), APPROVED, {"svc-1"}) == []
    assert validate(definition(nodes, edges), APPROVED, set()) == [
        "t: service message svc-1 not found"
    ]
