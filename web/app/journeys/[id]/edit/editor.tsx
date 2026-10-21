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
import {
  fromGraph,
  NEXT,
  targetsOf,
  toGraph,
  withTargets,
  type JourneyEdge,
  type JourneyNode,
} from "@/lib/journey-graph";
import type { Applied, TemplateOption } from "@/lib/node-forms";
import { saveDraft, type SaveResult } from "./actions";
import { JourneyNodeView } from "./journey-node";
import { NodePanel } from "./node-panel";

const nodeTypes: NodeTypes = { journey: JourneyNodeView };

export function Editor({
  journeyId,
  definition,
  layout,
  templates,
}: {
  journeyId: string;
  definition: Definition;
  layout: Layout;
  templates: TemplateOption[];
}) {
  const [initial] = useState(() => toGraph(definition, layout));
  const [nodes, setNodes, onNodesChange] = useNodesState<JourneyNode>(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<JourneyEdge>(initial.edges);
  const [result, setResult] = useState<SaveResult | null>(null);
  const [saving, startSaving] = useTransition();
  const [selectedId, setSelectedId] = useState<string | null>(null);

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

  const onSelectionChange = useCallback(
    ({ nodes: selected }: { nodes: { id: string }[] }) => setSelectedId(selected[0]?.id ?? null),
    [],
  );

  /** The side panel's Apply: new node data, and the node's outgoing edges rebuilt from it. */
  function apply(applied: Applied) {
    setNodes((current) =>
      current.map((node) => (node.id === applied.node.id ? { ...node, data: applied.node } : node)),
    );
    setEdges((current) => withTargets(current, applied.node.id, applied.targets));
  }

  function remove(id: string) {
    setNodes((current) => current.filter((node) => node.id !== id));
    setEdges((current) => current.filter((edge) => edge.source !== id && edge.target !== id));
    setSelectedId(null);
  }

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
  const selected = nodes.find((node) => node.id === selectedId);
  const targetOptions = nodes
    .filter((node) => node.id !== selectedId && node.data.type !== "start")
    .map((node) => node.id);
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
      <div style={{ display: "flex", gap: 16 }}>
        <div style={{ flex: 1, height: "70vh", border: "1px solid #ccc" }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onSelectionChange={onSelectionChange}
            deleteKeyCode={["Backspace", "Delete"]}
            fitView
          >
            <Background />
            <Controls />
          </ReactFlow>
        </div>
        {selected ? (
          <NodePanel
            key={selected.id}
            node={selected}
            targets={targetsOf(selected.id, edges)}
            options={targetOptions}
            templates={templates}
            onApply={apply}
            onDelete={remove}
          />
        ) : (
          <aside style={{ width: 320, fontSize: 14 }}>
            <p>Click a node to configure it and choose where it leads.</p>
          </aside>
        )}
      </div>
      <p>
        Connect nodes in the side panel or by dragging from a right handle to a left handle; select
        a node or edge and press Delete to remove it.
      </p>
    </>
  );
}
