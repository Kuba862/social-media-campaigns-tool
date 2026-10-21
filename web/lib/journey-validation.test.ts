import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import type { Condition, Definition, EdgeDef, NodeDef, Port } from "./journey-definition";
import { problemsOf, validate } from "./journey-validation";

/** The same cases as backend/tests/test_validation.py, so both sides must agree. */
const GUIDE: Definition = JSON.parse(
  readFileSync(
    new URL("../../backend/tests/fixtures/journey_guide_example.json", import.meta.url),
    "utf8",
  ),
);
const APPROVED = new Set(["tpl-1"]);

const start = (id = "start"): NodeDef => ({ id, type: "start" });
const end = (id = "end"): NodeDef => ({ id, type: "end" });
const wait = (id: string): NodeDef => ({ id, type: "wait", duration: "PT1H" });
const reply = (id: string): NodeDef => ({ id, type: "wait_for_reply", timeout: "PT1H" });
const update = (id: string): NodeDef => ({
  id,
  type: "update_contact",
  set: { "attributes.x": 1 },
});
const send = (id: string, template_id: string): NodeDef => ({
  id,
  type: "send_template",
  template_id,
  variables: {},
});
const branch = (id: string, conditions: Condition[], otherwise: string): NodeDef => ({
  id,
  type: "branch",
  conditions,
  else: otherwise,
});
const edge = (from: string, to: string, port?: Port): EdgeDef =>
  port ? { from, to, port } : { from, to };
const definition = (nodes: NodeDef[], edges: EdgeDef[]): Definition => ({
  schema_version: 1,
  nodes,
  edges,
});
const check = (nodes: NodeDef[], edges: EdgeDef[], approved = APPROVED) =>
  validate(definition(nodes, edges), approved);

describe("validate mirrors core/validation.py", () => {
  it("accepts the guide example and the minimal start-end journey", () => {
    expect(validate(GUIDE, APPROVED)).toEqual([]);
    expect(check([start(), end()], [edge("start", "end")])).toEqual([]);
  });

  it("checks ids, start and end nodes", () => {
    expect(check([start(), end(), end()], [edge("start", "end")])).toContain(
      "node ids must be unique",
    );
    expect(check([end()], [])).toEqual(["exactly one start node required, found 0"]);
    expect(
      check([start("s1"), start("s2"), end()], [edge("s1", "end"), edge("s2", "end")]),
    ).toEqual(["exactly one start node required, found 2"]);
    expect(check([start(), wait("w")], [edge("start", "w"), edge("w", "start")])).toEqual([
      "at least one end node required",
    ]);
  });

  it("reports unknown and unreachable nodes with the backend's wording", () => {
    const toGhost = check([start(), end()], [edge("start", "ghost")]);
    expect(toGhost).toContain("start points to unknown node ghost");
    expect(toGhost).toContain("unreachable nodes: ['end']");
    expect(check([start(), end()], [edge("start", "end"), edge("ghost", "end")])).toEqual([
      "edge from unknown node ghost",
    ]);
    const b = branch("b", [{ if: { "reply.text": "yes" }, next: "nowhere" }], "end");
    expect(check([start(), b, end()], [edge("start", "b")])).toEqual([
      "b points to unknown node nowhere",
    ]);
    expect(
      check([start(), end(), update("orphan")], [edge("start", "end"), edge("orphan", "end")]),
    ).toEqual(["unreachable nodes: ['orphan']"]);
  });

  it("checks the ports of every node type", () => {
    const nodes = [start(), reply("w"), end()];
    expect(check(nodes, [edge("start", "w"), edge("w", "end")])).toContain(
      "w: needs exactly one 'replied' and one 'timeout' edge",
    );
    expect(
      check(nodes, [edge("start", "w"), edge("w", "end", "replied"), edge("w", "end", "timeout")]),
    ).toEqual([]);
    const withBranch = check(
      [start(), branch("b", [], "end"), end()],
      [edge("start", "b"), edge("b", "end"), edge("end", "start")],
    );
    expect(withBranch).toContain("b: branch must not have edges");
    expect(withBranch).toContain("end: end must not have edges");
    const regular = [start(), wait("w"), end()];
    const message = "w: needs exactly one outgoing edge without a port";
    expect(check(regular, [edge("start", "w"), edge("w", "end", "replied")])).toContain(message);
    expect(check(regular, [edge("start", "w"), edge("w", "end"), edge("w", "end")])).toContain(
      message,
    );
    expect(check(regular, [edge("w", "end")])).toContain(
      "start: needs exactly one outgoing edge without a port",
    );
  });

  it("requires an approved template", () => {
    const nodes = [start(), send("s", "tpl-9"), end()];
    const edges = [edge("start", "s"), edge("s", "end")];
    expect(check(nodes, edges)).toEqual(["s: template tpl-9 is not APPROVED"]);
    expect(check(nodes, edges, new Set(["tpl-9"]))).toEqual([]);
  });

  it("rejects a cycle unless it passes through a wait", () => {
    const again = branch("b", [{ if: { "reply.text": "again" }, next: "a" }], "end");
    expect(
      check([start(), update("a"), again, end()], [edge("start", "a"), edge("a", "b")]),
    ).toEqual(["every cycle must pass through a wait or wait_for_reply node"]);
    expect(
      check(
        [start(), update("a"), wait("w"), again, end()],
        [edge("start", "a"), edge("a", "w"), edge("w", "b")],
      ),
    ).toEqual([]);
    expect(
      check(
        [start(), update("a"), reply("w"), again, end()],
        [
          edge("start", "a"),
          edge("a", "w"),
          edge("w", "b", "replied"),
          edge("w", "end", "timeout"),
        ],
      ),
    ).toEqual([]);
  });
});

describe("problemsOf", () => {
  it("names unfinished fields instead of echoing empty targets", () => {
    const nodes = [start(), send("s", ""), branch("b", [{ if: { a: "1" }, next: "" }], ""), end()];
    const edges = [edge("start", "s"), edge("s", "b")];
    const problems = problemsOf(definition(nodes, edges), APPROVED);
    expect(problems).toEqual([
      "s: choose a template",
      "b: condition 1 has no target",
      'b: "otherwise" has no target',
      "unreachable nodes: ['end']",
    ]);
  });

  it("is empty for the guide journey", () => {
    expect(problemsOf(GUIDE, APPROVED)).toEqual([]);
  });
});
