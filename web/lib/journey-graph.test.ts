import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { newNode, nextId, type Definition, type Layout } from "./journey-definition";
import { fromGraph, sourceHandles, toGraph } from "./journey-graph";

/** The guide's section 4.1 journey, shared with the backend tests. */
const GUIDE: Definition = JSON.parse(
  readFileSync(
    new URL("../../backend/tests/fixtures/journey_guide_example.json", import.meta.url),
    "utf8",
  ),
);
const LAYOUT: Layout = Object.fromEntries(
  GUIDE.nodes.map((node, index) => [node.id, { x: index * 200, y: 40 }]),
);

describe("toGraph and fromGraph", () => {
  it("round-trip the guide journey and its layout", () => {
    const graph = toGraph(GUIDE, LAYOUT);
    expect(graph.nodes.map((node) => node.id)).toEqual(GUIDE.nodes.map((node) => node.id));
    expect(fromGraph(graph.nodes, graph.edges)).toEqual({ definition: GUIDE, layout: LAYOUT });
  });

  it("turn branch targets into edges from the condition and else handles, and back", () => {
    const { nodes, edges } = toGraph(GUIDE, LAYOUT);
    const fromBranch = edges.filter((edge) => edge.source === "n4");
    expect(fromBranch.map((edge) => [edge.sourceHandle, edge.target])).toEqual([
      ["cond-0", "n5"],
      ["else", "end"],
    ]);
    const rewired = edges.map((edge) =>
      edge.source === "n4" && edge.sourceHandle === "cond-0" ? { ...edge, target: "end" } : edge,
    );
    const branch = fromGraph(nodes, rewired).definition.nodes.find((node) => node.id === "n4");
    expect(branch).toEqual({
      id: "n4",
      type: "branch",
      conditions: [{ if: { "reply.button_payload": "YES" }, next: "end" }],
      else: "end",
    });
  });

  it("keeps wait_for_reply ports and drops nothing but branch edges from the edge list", () => {
    const { nodes, edges } = toGraph(GUIDE, LAYOUT);
    expect(fromGraph(nodes, edges).definition.edges).toEqual(GUIDE.edges);
  });

  it("gives a node without a saved position a default and an unconnected handle an empty target", () => {
    const definition: Definition = {
      schema_version: 1,
      nodes: [
        { id: "start", type: "start" },
        {
          id: "branch_1",
          type: "branch",
          conditions: [{ if: { "reply.text": "a" }, next: "" }],
          else: "",
        },
      ],
      edges: [],
    };
    const graph = toGraph(definition, {});
    expect(graph.nodes[1].position).toEqual({ x: 220, y: 0 });
    expect(graph.edges).toEqual([]);
    expect(fromGraph(graph.nodes, graph.edges).definition).toEqual(definition);
  });
});

describe("node helpers", () => {
  it("offers the handles the definition allows", () => {
    expect(sourceHandles(newNode("end", "e"))).toEqual([]);
    expect(sourceHandles(newNode("wait_for_reply", "w"))).toEqual(["replied", "timeout"]);
    expect(sourceHandles(newNode("branch", "b"))).toEqual(["else"]);
    expect(sourceHandles(newNode("wait", "p"))).toEqual(["next"]);
  });

  it("picks the next free id per type", () => {
    const existing = [{ id: "wait_1" }, { id: "wait_2" }, { id: "end" }];
    expect(nextId(existing, "wait")).toBe("wait_3");
    expect(nextId(existing, "branch")).toBe("branch_1");
  });
});
