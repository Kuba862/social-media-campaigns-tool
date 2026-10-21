"use client";

import { useCallback, useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  addEdge,
  Background,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesInitialized,
  useNodesState,
  useReactFlow,
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
import { problemsOf } from "@/lib/journey-validation";
import type { Applied, TemplateOption } from "@/lib/node-forms";
import { publishDraft, saveDraft, type SaveResult } from "./actions";
import { JourneyNodeView } from "./journey-node";
import { NodePanel } from "./node-panel";

const nodeTypes: NodeTypes = { journey: JourneyNodeView };

type EditorProps = {
  journeyId: string;
  definition: Definition;
  layout: Layout;
  templates: TemplateOption[];
};

/** The provider lets the editor refit the view after the palette adds a node. */
export function Editor(props: EditorProps) {
  return (
    <ReactFlowProvider>
      <EditorInner {...props} />
    </ReactFlowProvider>
  );
}

function EditorInner({ journeyId, definition, layout, templates }: EditorProps) {
  const router = useRouter();
  const [initial] = useState(() => toGraph(definition, layout));
  const [nodes, setNodes, onNodesChange] = useNodesState<JourneyNode>(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<JourneyEdge>(initial.edges);
  const [result, setResult] = useState<SaveResult | null>(null);
  const [serverProblems, setServerProblems] = useState<string[]>([]);
  const [saving, startSaving] = useTransition();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { fitView } = useReactFlow();
  const nodesInitialized = useNodesInitialized();
  useEffect(() => {
    if (nodesInitialized) void fitView({ padding: 0.25, maxZoom: 1 });
  }, [nodesInitialized, fitView]);

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
      const x = current.length === 0 ? 0 : Math.max(...current.map((n) => n.position.x)) + 240;
      return [...current, { id, type: "journey", position: { x, y: 0 }, data: newNode(type, id) }];
    });
  }

  function save() {
    const draft = fromGraph(nodes, edges);
    startSaving(async () => {
      setResult(await saveDraft(journeyId, draft.definition, draft.layout));
    });
  }

  /** Save, then publish; on success the journey page shows the new version. */
  function publish() {
    const draft = fromGraph(nodes, edges);
    startSaving(async () => {
      const outcome = await publishDraft(journeyId, draft.definition, draft.layout);
      if (outcome.ok) {
        router.push(`/journeys/${journeyId}`);
      } else {
        setServerProblems(outcome.problems);
      }
    });
  }

  const hasStart = nodes.some((node) => node.data.type === "start");
  const approved = new Set(templates.map((template) => template.id));
  const problems = problemsOf(fromGraph(nodes, edges).definition, approved);
  const selected = nodes.find((node) => node.id === selectedId);
  const targetOptions = nodes
    .filter((node) => node.id !== selectedId && node.data.type !== "start")
    .map((node) => node.id);
  return (
    <>
      <div className="toolbar">
        {NODE_TYPES.map((type) => (
          <button
            key={type}
            type="button"
            onClick={() => add(type)}
            disabled={type === "start" && hasStart}
            className="secondary"
          >
            Add {type}
          </button>
        ))}
        <span className="spacer" />
        <button type="button" onClick={save} disabled={saving}>
          Save draft
        </button>
        <button type="button" onClick={publish} disabled={saving || problems.length > 0}>
          Publish
        </button>
      </div>
      <p role="status">
        {result === null ? "" : result.ok ? `Draft v${result.version} saved` : result.error}
      </p>
      {problems.length === 0 ? (
        <p className="muted">Ready to publish.</p>
      ) : (
        <ul aria-label="Problems" className="problems">
          {problems.map((problem) => (
            <li key={problem}>{problem}</li>
          ))}
        </ul>
      )}
      {serverProblems.length > 0 && (
        <ul aria-label="Server problems" role="alert">
          {serverProblems.map((problem) => (
            <li key={problem}>{problem}</li>
          ))}
        </ul>
      )}
      <div className="editor">
        <div className="canvas">
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
            fitViewOptions={{ padding: 0.25, maxZoom: 1 }}
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
          <aside className="panel">
            <p className="muted">Click a node to configure it and choose where it leads.</p>
          </aside>
        )}
      </div>
      <p className="muted">
        Connect nodes in the side panel or by dragging from a right handle to a left handle; select
        a node or edge and press Delete to remove it.
      </p>
    </>
  );
}
