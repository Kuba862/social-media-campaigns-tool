/** The journey definition JSON as the engine reads it (backend core/journey_schema.py). */

export type NodeType =
  | "start"
  | "send_template"
  | "send_text"
  | "wait"
  | "wait_for_reply"
  | "branch"
  | "update_contact"
  | "end";

export const NODE_TYPES: NodeType[] = [
  "start",
  "send_template",
  "send_text",
  "wait",
  "wait_for_reply",
  "branch",
  "update_contact",
  "end",
];

export type Condition = { if: Record<string, string>; next: string };
/** What a send_text node does when the contact's 24-hour window is closed. */
export type IfClosed = "skip" | "fail";

/** A draft may hold unfinished nodes (empty template, empty else); publishing validates them. */
export type NodeDef =
  | { id: string; type: "start" }
  | { id: string; type: "send_template"; template_id: string; variables: Record<string, string> }
  | { id: string; type: "send_text"; text: string; if_closed: IfClosed; message_id?: string | null }
  | { id: string; type: "wait"; duration: string }
  | { id: string; type: "wait_for_reply"; timeout: string }
  | { id: string; type: "branch"; conditions: Condition[]; else: string }
  | { id: string; type: "update_contact"; set: Record<string, unknown> }
  | { id: string; type: "end" };

export type Port = "replied" | "timeout";
export type EdgeDef = { from: string; to: string; port?: Port };

export type Definition = { schema_version: 1; nodes: NodeDef[]; edges: EdgeDef[] };
export type Point = { x: number; y: number };
export type Layout = Record<string, Point>;

export const EMPTY_DEFINITION: Definition = {
  schema_version: 1,
  nodes: [
    { id: "start", type: "start" },
    { id: "end", type: "end" },
  ],
  edges: [],
};
export const EMPTY_LAYOUT: Layout = { start: { x: 0, y: 0 }, end: { x: 600, y: 0 } };

/** A fresh node with the defaults a draft may keep until the side panel fills them in. */
export function newNode(type: NodeType, id: string): NodeDef {
  switch (type) {
    case "start":
      return { id, type };
    case "send_template":
      return { id, type, template_id: "", variables: {} };
    case "send_text":
      return { id, type, text: "", if_closed: "skip", message_id: null };
    case "wait":
      return { id, type, duration: "PT1H" };
    case "wait_for_reply":
      return { id, type, timeout: "PT24H" };
    case "branch":
      return { id, type, conditions: [], else: "" };
    case "update_contact":
      return { id, type, set: {} };
    case "end":
      return { id, type };
  }
}

/** "wait_1", "wait_2", ... whichever is free among the existing ids. */
export function nextId(existing: { id: string }[], type: NodeType): string {
  let n = 1;
  while (existing.some((node) => node.id === `${type}_${n}`)) n += 1;
  return `${type}_${n}`;
}
