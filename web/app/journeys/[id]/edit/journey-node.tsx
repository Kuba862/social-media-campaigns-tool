"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { NodeDef } from "@/lib/journey-definition";
import { sourceHandles, type JourneyNode } from "@/lib/journey-graph";

function summary(node: NodeDef): string {
  switch (node.type) {
    case "send_template":
      return node.template_id ? `template ${node.template_id.slice(0, 8)}…` : "no template";
    case "send_text":
      return node.text
        ? `"${node.text.slice(0, 22)}${node.text.length > 22 ? "…" : ""}"`
        : "no text";
    case "wait":
      return node.duration;
    case "wait_for_reply":
      return `timeout ${node.timeout}`;
    case "branch":
      return `${node.conditions.length} condition(s)`;
    case "update_contact":
      return Object.keys(node.set).join(", ") || "(nothing)";
    default:
      return "";
  }
}

/** One box per node: type, id, a one-line summary, a target handle and the source handles. */
export function JourneyNodeView({ id, data }: NodeProps<JourneyNode>) {
  const handles = sourceHandles(data);
  return (
    <div className="node" data-type={data.type}>
      {data.type !== "start" && <Handle type="target" position={Position.Left} id="in" />}
      <strong>{data.type.replace("_", " ")}</strong>
      <div className="id">{id}</div>
      <div className="summary">{summary(data)}</div>
      {handles.length > 1 && (
        <div className="handles">
          {handles.map((handle) => (
            <div key={handle}>{handle}</div>
          ))}
        </div>
      )}
      {handles.map((handle, index) => (
        <Handle
          key={handle}
          type="source"
          position={Position.Right}
          id={handle}
          title={handle}
          style={{ top: `${((index + 1) * 100) / (handles.length + 1)}%` }}
        />
      ))}
    </div>
  );
}
