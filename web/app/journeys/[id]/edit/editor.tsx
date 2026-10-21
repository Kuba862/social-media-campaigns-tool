"use client";

import { useCallback, useState, useTransition } from "react";
import {
  addEdge,
  Background,
  Controls,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Connection,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  NODE_TYPES,
  newNode,
  nextId,
  type Definition,
  type Layout,
  type NodeType,
} from "@/lib/journey-definition";
import { fromGraph, NEXT, toGraph, type JourneyEdge, type JourneyNode } from "@/lib/journey-graph";
import { saveDraft, type SaveResult } from "./actions";
import { JourneyNodeView } from "./journey-node";

const nodeTypes: NodeTypes = { journey: JourneyNodeView };

export function Editor({
  journeyId,
  definition,
  layout,
}: {
  journeyId: string;
  definition: Definition;
  layout: Layout;
}) {
  const [initial] = useState(() => toGraph(definition, layout));
  const [nodes, setNodes, onNodesChange] = useNodesState<JourneyNode>(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<JourneyEdge>(initial.edges);
  const [result, setResult] = useState<SaveResult | null>(null);
  const [saving, startSaving] = useTransition();

  /** A source handle leads to one node: connecting again replaces the previous edge. */
  const onConnect = useCallback(
    (connection: Connection) => {
      const handle = connection.sourceHandle ?? NEXT;
      setEdges((current) =>
        addEdge(
          connection,
          current.filter(
            (edge) =>
              !(edge.source === connection.source && (edge.sourceHandle ?? NEXT) === handle),
          ),
        ),
      );
    },
    [setEdges],
  );

  function add(type: NodeType) {
    setNodes((current) => {
      const id = nextId(current, type);
      const x = current.length === 0 ? 0 : Math.max(...current.map((n) => n.position.x)) + 220;
      return [...current, { id, type: "journey", position: { x, y: 0 }, data: newNode(type, id) }];
    });
  }

  function save() {
    const draft = fromGraph(nodes, edges);
    startSaving(async () => {
      setResult(await saveDraft(journeyId, draft.definition, draft.layout));
    });
  }

  const hasStart = nodes.some((node) => node.data.type === "start");
  return (
    <>
      <p>
        {NODE_TYPES.map((type) => (
          <button
            key={type}
            type="button"
            onClick={() => add(type)}
            disabled={type === "start" && hasStart}
          >
            Add {type}
          </button>
        ))}{" "}
        <button type="button" onClick={save} disabled={saving}>
          Save draft
        </button>
      </p>
      <p role="status">
        {result === null ? "" : result.ok ? `Draft v${result.version} saved` : result.error}
      </p>
      <div style={{ height: "70vh", border: "1px solid #ccc" }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          deleteKeyCode={["Backspace", "Delete"]}
          fitView
        >
          <Background />
          <Controls />
        </ReactFlow>
      </div>
      <p>
        Drag from a node&apos;s right handle to another node&apos;s left handle to connect them;
        select a node or edge and press Delete to remove it. Node settings come with the side panel.
      </p>
    </>
  );
}
