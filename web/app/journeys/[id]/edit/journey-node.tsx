"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { NodeDef } from "@/lib/journey-definition";
import { sourceHandles, type JourneyNode } from "@/lib/journey-graph";

function summary(node: NodeDef): string {
  switch (node.type) {
    case "send_template":
      return `template: ${node.template_id || "(none)"}`;
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
    <div
      style={{
        border: "1px solid #333",
        borderRadius: 6,
        padding: "6px 10px",
        background: "#fff",
        minWidth: 150,
        fontSize: 12,
      }}
    >
      {data.type !== "start" && <Handle type="target" position={Position.Left} id="in" />}
      <strong>{data.type}</strong>
      <div>{id}</div>
      <div>{summary(data)}</div>
      {handles.length > 1 && (
        <div style={{ textAlign: "right", color: "#555" }}>
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
