import { useMemo, useRef, useState } from "react";
import {
  CircleDot,
  Eye,
  GitBranch,
  Lightbulb,
  LockKeyhole,
  Pencil,
  Play,
  StickyNote,
  TriangleAlert,
  UserRound,
} from "./icons";
import type { Lens, ViewEdge, ViewGraph, ViewNode } from "./api";
import { shortId } from "./api";

type Position = { x: number; y: number };
type Props = {
  graph: ViewGraph;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onAdd: () => void;
  onConnect: (source: string, target: string) => void;
  pendingSource: string | null;
  lens: Lens;
};

const width = 224;
const height = 100;

function layout(graph: ViewGraph): {
  positions: Record<string, Position>;
  canvasWidth: number;
  canvasHeight: number;
} {
  const positions: Record<string, Position> = {};
  const nodes = graph.nodes;
  if (graph.lens === "story") {
    nodes.forEach((node, index) => {
      positions[node.id] = { x: 74 + index * 260, y: 110 };
    });
    return {
      positions,
      canvasWidth: Math.max(800, 160 + nodes.length * 260),
      canvasHeight: 480,
    };
  }
  if (graph.lens === "discourse") {
    const acts = nodes.filter((n) => n.kind === "discourse_act");
    const story = nodes.filter((n) => n.kind === "story_event");
    acts.forEach((node, index) => {
      positions[node.id] = { x: 74 + index * 260, y: 85 };
    });
    story.forEach((node, index) => {
      positions[node.id] = { x: 74 + index * 260, y: 355 };
    });
    return {
      positions,
      canvasWidth: Math.max(
        800,
        180 + Math.max(acts.length, story.length) * 260,
      ),
      canvasHeight: 610,
    };
  }
  if (graph.lens === "pipeline") {
    nodes.forEach((node, index) => {
      positions[node.id] = {
        x: 65 + (index % 7) * 244,
        y: 85 + Math.floor(index / 7) * 150,
      };
    });
    return { positions, canvasWidth: 1810, canvasHeight: 780 };
  }
  nodes.forEach((node, index) => {
    positions[node.id] = {
      x: 74 + (index % 5) * 264,
      y: 90 + Math.floor(index / 5) * 160,
    };
  });
  return {
    positions,
    canvasWidth: Math.max(900, 90 + Math.min(5, nodes.length) * 264),
    canvasHeight: Math.max(480, 220 + Math.ceil(nodes.length / 5) * 160),
  };
}

function iconFor(node: ViewNode) {
  if (node.kind === "actor") return <UserRound size={17} />;
  if (node.kind === "interpretation") return <Lightbulb size={17} />;
  if (node.kind === "evidence" || node.kind === "claim")
    return <StickyNote size={17} />;
  if (node.kind === "appearance" || node.kind === "object")
    return <CircleDot size={17} />;
  if (node.kind === "stage") return <Play size={17} />;
  if (node.kind === "story_event" && node.fields.kind === "observation")
    return <Eye size={17} />;
  if (node.kind === "story_event" && node.fields.kind === "crisis")
    return <TriangleAlert size={17} />;
  if (node.kind === "story_event") return <GitBranch size={17} />;
  return <CircleDot size={17} />;
}

function GraphEdge({
  edge,
  positions,
}: {
  edge: ViewEdge;
  positions: Record<string, Position>;
}) {
  const a = positions[edge.source],
    b = positions[edge.target];
  if (!a || !b) return null;
  const x1 = a.x + width,
    y1 = a.y + height / 2,
    x2 = b.x,
    y2 = b.y + height / 2;
  const dx = Math.max(48, Math.abs(x2 - x1) * 0.42);
  const path =
    edge.kind === "retrospects"
      ? `M ${x1} ${y1} C ${x1 + 70} ${y1 + 180}, ${x2 - 70} ${y2 + 180}, ${x2} ${y2}`
      : `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
  const labelX = (x1 + x2) / 2,
    labelY =
      edge.kind === "retrospects" ? Math.max(y1, y2) + 125 : (y1 + y2) / 2 - 10;
  return (
    <g
      className={`graph-edge edge-${edge.kind} ${edge.state === "draft" ? "edge-draft" : ""}`}
    >
      <path d={path} fill="none" markerEnd="url(#arrow)" />
      {edge.kind !== "flows" && (
        <text x={labelX} y={labelY} textAnchor="middle">
          {edge.kind}
        </text>
      )}
    </g>
  );
}

export default function GraphCanvas({
  graph,
  selectedId,
  onSelect,
  onAdd,
  onConnect,
  pendingSource,
  lens,
}: Props) {
  const { positions, canvasWidth, canvasHeight } = useMemo(
    () => layout(graph),
    [graph],
  );
  const [zoom, setZoom] = useState(1);
  const scrollRef = useRef<HTMLDivElement>(null);
  function activate(id: string) {
    if (pendingSource && pendingSource !== id) onConnect(pendingSource, id);
    else onSelect(id);
  }
  const labels: Record<string, string> = {
    story: "STORY TIME →",
    discourse: "TELLING ORDER →",
    pipeline: "RUN STAGES →",
  };
  return (
    <div className="graph-shell">
      <div className="graph-tools">
        <span className="graph-eyebrow">
          {labels[lens] ?? `${lens.toUpperCase()} LENS`}
        </span>
        <span className="graph-count">
          {graph.nodes.length} nodes · {graph.edges.length} links
        </span>
        <div className="spacer" />
        <button
          className="tiny-button"
          onClick={() => setZoom((z) => Math.max(0.55, +(z - 0.15).toFixed(2)))}
          aria-label="Zoom out"
        >
          −
        </button>
        <span className="zoom-label">{Math.round(zoom * 100)}%</span>
        <button
          className="tiny-button"
          onClick={() => setZoom((z) => Math.min(1.5, +(z + 0.15).toFixed(2)))}
          aria-label="Zoom in"
        >
          +
        </button>
        <button
          className="tiny-button fit-button"
          onClick={() => {
            setZoom(1);
            scrollRef.current?.scrollTo({
              left: 0,
              top: 0,
              behavior: "smooth",
            });
          }}
        >
          Fit
        </button>
      </div>
      {pendingSource && (
        <div className="connect-banner">
          Select a target node to connect. Press Esc to cancel.
        </div>
      )}
      <div
        ref={scrollRef}
        className="graph-scroll"
        role="application"
        aria-label={`${lens} graph canvas`}
      >
        <div
          className="graph-stage"
          style={{ width: canvasWidth * zoom, height: canvasHeight * zoom }}
          onDoubleClick={(event) => {
            if (event.target === event.currentTarget) onAdd();
          }}
        >
          <div
            style={{
              width: canvasWidth,
              height: canvasHeight,
              transform: `scale(${zoom})`,
              transformOrigin: "top left",
              position: "relative",
            }}
          >
            <div className="canvas-grid" />
            {lens === "discourse" && (
              <>
                <div className="lane-label" style={{ top: 52 }}>
                  DISCOURSE ACTS
                </div>
                <div className="lane-label" style={{ top: 322 }}>
                  STORY EVENTS
                </div>
              </>
            )}
            {lens === "pipeline" &&
              ["C0", "C1", "C2", "C3"].map((condition, i) => (
                <div
                  key={condition}
                  className="lane-label"
                  style={{ top: 56 + i * 150 }}
                >
                  {condition}
                </div>
              ))}
            <svg
              className="graph-lines"
              width={canvasWidth}
              height={canvasHeight}
              aria-hidden="true"
            >
              <defs>
                <marker
                  id="arrow"
                  markerWidth="8"
                  markerHeight="8"
                  refX="7"
                  refY="4"
                  orient="auto"
                >
                  <path d="M0 0 L8 4 L0 8" fill="#9aa8b8" />
                </marker>
              </defs>
              {graph.edges.map((edge) => (
                <GraphEdge key={edge.id} edge={edge} positions={positions} />
              ))}
            </svg>
            {graph.nodes.map((node) => (
              <button
                key={node.id}
                type="button"
                className={`graph-node kind-${node.kind} family-${node.kind === "discourse_act" ? "telling" : ["interpretation", "model_version", "belief", "concept", "scenario", "crisis"].includes(node.kind) ? "mind" : ["stage", "claim", "evidence", "appearance"].includes(node.kind) ? "neutral" : "world"} node-${node.state} ${selectedId === node.id ? "is-selected" : ""} ${pendingSource === node.id ? "is-source" : ""}`}
                style={{
                  left: positions[node.id]?.x ?? 0,
                  top: positions[node.id]?.y ?? 0,
                }}
                onClick={() => activate(node.id)}
                aria-label={node.textAlt}
                aria-pressed={selectedId === node.id}
              >
                <span className="node-top">
                  <span className="node-icon">{iconFor(node)}</span>
                  <span className="node-kind">
                    {node.kind.replace("_", " ")}
                  </span>
                  <span className="node-index">
                    {node.refs.sequence
                      ? String(node.refs.sequence).padStart(2, "0")
                      : ""}
                  </span>
                </span>
                <span className="node-title">{node.title}</span>
                <span className="node-bottom">
                  <span className="node-id">{shortId(node.id)}</span>
                  <span className="node-status">
                    {node.state === "draft" ? (
                      <Pencil size={13} />
                    ) : (
                      <LockKeyhole size={13} />
                    )}
                    {node.state}
                  </span>
                </span>
              </button>
            ))}
            {!graph.nodes.length && (
              <div className="canvas-empty">
                <p>No nodes in this lens yet.</p>
                {(lens === "story" || lens === "discourse") && (
                  <button className="primary" onClick={onAdd}>
                    Add the first node
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
