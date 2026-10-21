import type { Edge, Node } from "@xyflow/react";
import type { Definition, EdgeDef, Layout, NodeDef, Point } from "./journey-definition";

export type JourneyNode = Node<NodeDef, "journey">;
export type JourneyEdge = Edge;

/** The single source handle of start, send_template, wait and update_contact. */
export const NEXT = "next";
export const ELSE = "else";
export const conditionHandle = (index: number): string => `cond-${index}`;

/** Source handles a node offers on the canvas; the definition decides, not the user. */
export function sourceHandles(node: NodeDef): string[] {
  switch (node.type) {
    case "end":
      return [];
    case "wait_for_reply":
      return ["replied", "timeout"];
    case "branch":
      return [...node.conditions.map((_, index) => conditionHandle(index)), ELSE];
    default:
      return [NEXT];
  }
}

function edgeId(source: string, handle: string, target: string): string {
  return `${source}:${handle}->${target}`;
}

function flowEdge(source: string, handle: string, target: string): JourneyEdge {
  return { id: edgeId(source, handle, target), source, sourceHandle: handle, target };
}

/**
 * Definition plus layout -> React Flow nodes and edges. Branch targets live inside the branch
 * node (conditions[i].next, else) in the definition; on the canvas they become edges from the
 * handles cond-i and else.
 */
export function toGraph(
  definition: Definition,
  layout: Layout,
): { nodes: JourneyNode[]; edges: JourneyEdge[] } {
  const nodes: JourneyNode[] = definition.nodes.map((node, index) => {
    const position: Point | undefined = layout[node.id];
    return {
      id: node.id,
      type: "journey",
      position: position ?? { x: index * 220, y: 0 },
      data: node,
    };
  });
  const edges = definition.edges.map((edge) => flowEdge(edge.from, edge.port ?? NEXT, edge.to));
  for (const node of definition.nodes) {
    if (node.type !== "branch") continue;
    node.conditions.forEach((condition, index) => {
      if (condition.next) edges.push(flowEdge(node.id, conditionHandle(index), condition.next));
    });
    if (node.else) edges.push(flowEdge(node.id, ELSE, node.else));
  }
  return { nodes, edges };
}

/** Handle -> target for a node's current outgoing edges. */
export function targetsOf(nodeId: string, edges: JourneyEdge[]): Record<string, string> {
  const targets: Record<string, string> = {};
  for (const edge of edges) {
    if (edge.source === nodeId) targets[edge.sourceHandle ?? NEXT] = edge.target;
  }
  return targets;
}

/** Replace a node's outgoing edges with the given handle -> target map ("" means none). */
export function withTargets(
  edges: JourneyEdge[],
  nodeId: string,
  targets: Record<string, string>,
): JourneyEdge[] {
  const kept = edges.filter((edge) => edge.source !== nodeId);
  const added = Object.entries(targets)
    .filter(([, target]) => target !== "")
    .map(([handle, target]) => flowEdge(nodeId, handle, target));
  return [...kept, ...added];
}

/** The inverse of toGraph: what the editor saves as the draft. Positions are rounded. */
export function fromGraph(
  nodes: JourneyNode[],
  edges: JourneyEdge[],
): { definition: Definition; layout: Layout } {
  const targetOf = (source: string, handle: string): string =>
    edges.find((edge) => edge.source === source && (edge.sourceHandle ?? NEXT) === handle)
      ?.target ?? "";
  const defNodes: NodeDef[] = nodes.map((node) => {
    const data = { ...node.data, id: node.id };
    if (data.type !== "branch") return data;
    return {
      ...data,
      conditions: data.conditions.map((condition, index) => ({
        ...condition,
        next: targetOf(node.id, conditionHandle(index)),
      })),
      else: targetOf(node.id, ELSE),
    };
  });
  const defEdges: EdgeDef[] = [];
  for (const edge of edges) {
    const handle = edge.sourceHandle ?? NEXT;
    if (handle === NEXT) defEdges.push({ from: edge.source, to: edge.target });
    else if (handle === "replied" || handle === "timeout") {
      defEdges.push({ from: edge.source, to: edge.target, port: handle });
    }
  }
  const layout: Layout = {};
  for (const node of nodes) {
    layout[node.id] = { x: Math.round(node.position.x), y: Math.round(node.position.y) };
  }
  return { definition: { schema_version: 1, nodes: defNodes, edges: defEdges }, layout };
}
