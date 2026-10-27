/**
 * Graph rules, a mirror of backend core/validation.py with the same messages. The server stays
 * authoritative at publish time; this lets the editor show the problems as the user works.
 */
import type { Definition } from "./journey-definition";

const WAIT_TYPES = new Set(["wait", "wait_for_reply"]);

function push(map: Map<string, string[]>, key: string, ...values: string[]): void {
  const list = map.get(key);
  if (list) list.push(...values);
  else map.set(key, [...values]);
}

/** Adjacency list: edges plus branch targets (a branch keeps its targets in the node). */
export function successors(defn: Definition): Map<string, string[]> {
  const succ = new Map<string, string[]>(defn.nodes.map((node) => [node.id, []]));
  for (const edge of defn.edges) push(succ, edge.from, edge.to);
  for (const node of defn.nodes) {
    if (node.type === "branch") {
      push(succ, node.id, ...node.conditions.map((condition) => condition.next), node.else);
    }
  }
  return succ;
}

export function validate(defn: Definition, approvedTemplateIds: Set<string>): string[] {
  const errors: string[] = [];
  const ids = defn.nodes.map((node) => node.id);
  const known = new Set(ids);
  if (ids.length !== known.size) errors.push("node ids must be unique");

  const starts = defn.nodes.filter((node) => node.type === "start").map((node) => node.id);
  if (starts.length !== 1) errors.push(`exactly one start node required, found ${starts.length}`);
  if (!defn.nodes.some((node) => node.type === "end"))
    errors.push("at least one end node required");

  const succ = successors(defn);
  for (const [source, targets] of succ) {
    if (!known.has(source)) errors.push(`edge from unknown node ${source}`);
    for (const target of targets) {
      if (!known.has(target)) errors.push(`${source} points to unknown node ${target}`);
    }
  }

  errors.push(...portErrors(defn));
  for (const node of defn.nodes) {
    if (node.type === "send_template" && !approvedTemplateIds.has(node.template_id)) {
      errors.push(`${node.id}: template ${node.template_id} is not APPROVED`);
    }
  }

  if (starts.length === 1) {
    const seen = reachable(starts[0], succ);
    const unreachable = [...known].filter((id) => !seen.has(id)).sort();
    if (unreachable.length > 0) {
      errors.push(`unreachable nodes: [${unreachable.map((id) => `'${id}'`).join(", ")}]`);
    }
  }

  if (hasCycleWithoutWait(defn, succ)) {
    errors.push("every cycle must pass through a wait or wait_for_reply node");
  }
  return errors;
}

function portErrors(defn: Definition): string[] {
  const ports = new Map<string, string[]>(defn.nodes.map((node) => [node.id, []]));
  for (const edge of defn.edges) {
    if (ports.has(edge.from)) push(ports, edge.from, edge.port ?? "");
  }
  const errors: string[] = [];
  for (const node of defn.nodes) {
    const out = ports.get(node.id) ?? [];
    if (node.type === "wait_for_reply") {
      const sorted = [...out].sort();
      if (sorted.length !== 2 || sorted[0] !== "replied" || sorted[1] !== "timeout") {
        errors.push(`${node.id}: needs exactly one 'replied' and one 'timeout' edge`);
      }
    } else if (node.type === "branch" || node.type === "end") {
      if (out.length > 0) errors.push(`${node.id}: ${node.type} must not have edges`);
    } else if (!(out.length === 1 && out[0] === "")) {
      errors.push(`${node.id}: needs exactly one outgoing edge without a port`);
    }
  }
  return errors;
}

function reachable(start: string, succ: Map<string, string[]>): Set<string> {
  const seen = new Set([start]);
  const queue = [start];
  while (queue.length > 0) {
    const current = queue.shift() as string;
    for (const next of succ.get(current) ?? []) {
      if (!seen.has(next)) {
        seen.add(next);
        queue.push(next);
      }
    }
  }
  return seen;
}

function hasCycleWithoutWait(defn: Definition, succ: Map<string, string[]>): boolean {
  const waits = new Set(defn.nodes.filter((n) => WAIT_TYPES.has(n.type)).map((n) => n.id));
  const graph = new Map<string, string[]>();
  for (const [source, targets] of succ) {
    if (!waits.has(source))
      graph.set(
        source,
        targets.filter((target) => !waits.has(target)),
      );
  }
  const state = new Map<string, "open" | "done">();
  const visit = (node: string): boolean => {
    state.set(node, "open");
    for (const next of graph.get(node) ?? []) {
      if (state.get(next) === "open" || (!state.has(next) && visit(next))) return true;
    }
    state.set(node, "done");
    return false;
  };
  for (const node of graph.keys()) {
    if (!state.has(node) && visit(node)) return true;
  }
  return false;
}

/** What the editor still has to fill in, said more kindly than the graph rules would. */
export function unfinished(defn: Definition): string[] {
  const problems: string[] = [];
  for (const node of defn.nodes) {
    if (node.type === "send_template" && node.template_id === "") {
      problems.push(`${node.id}: choose a template`);
    }
    if (node.type === "send_text" && node.text.trim() === "") {
      problems.push(`${node.id}: write the text`);
    }
    if (node.type === "branch") {
      node.conditions.forEach((condition, index) => {
        if (condition.next === "")
          problems.push(`${node.id}: condition ${index + 1} has no target`);
      });
      if (node.else === "") problems.push(`${node.id}: "otherwise" has no target`);
    }
  }
  return problems;
}

/** The editor's list: unfinished fields first, then the graph rules minus their echoes. */
export function problemsOf(defn: Definition, approvedTemplateIds: Set<string>): string[] {
  const pending = unfinished(defn);
  const rules = validate(defn, approvedTemplateIds).filter(
    (message) =>
      !message.endsWith("unknown node ") && !message.endsWith("template  is not APPROVED"),
  );
  return [...pending, ...rules];
}
