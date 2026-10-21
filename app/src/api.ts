import { invoke } from "@tauri-apps/api/core";
import type { Fixture, NarrativeContract } from "./generated/contracts";

export type Lens =
  | "fixture"
  | "story"
  | "discourse"
  | "mind"
  | "provenance"
  | "motif"
  | "pipeline";
export type NodeState =
  | "draft"
  | "sealed"
  | "proposed"
  | "rejected"
  | "invalid";
export interface ViewNode {
  id: string;
  kind: string;
  title: string;
  fields: Record<string, unknown>;
  state: NodeState;
  lens: Lens;
  refs: { branchId: string; sequence?: number };
  badges: { code: string; count: number }[];
  textAlt: string;
}
export interface ViewEdge {
  id: string;
  source: string;
  target: string;
  kind: string;
  state: NodeState;
}
export interface ViewGraph {
  lens: Lens;
  branchId: string;
  nodes: ViewNode[];
  edges: ViewEdge[];
  groups: unknown[];
  protocolVersion: string;
}
export interface DraftNode {
  id: string;
  title: string;
  fields: Record<string, unknown>;
}
export interface Draft {
  id: string;
  branch_id: string;
  lens: Lens;
  nodes: DraftNode[];
  edges: ViewEdge[];
}
export interface Branch {
  branch_id: string;
  name?: string;
  condition?: string;
  parent: string | null;
  fork_sequence: number;
}
export interface ProjectSummary {
  path: string;
  name: string;
  active_branch: string;
  read_only?: boolean;
  branches: Branch[];
  fixture: Fixture;
  contract: NarrativeContract;
}
export interface Finding {
  code: string;
  layer: string;
  message: string;
}
export interface RunResult {
  run_id: string;
  branch_id: string;
  status: string;
  conditions: string[];
  prose: string;
  findings: Finding[];
  stages: { condition: string; stage: string; status: string }[];
  packet_hash: string;
  projection_hashes: Record<string, string>;
}

export const LENSES: { id: Lens; label: string; question: string }[] = [
  {
    id: "fixture",
    label: "Fixture",
    question: "Who and what is in this scene?",
  },
  { id: "story", label: "Story", question: "What happens, when, and why?" },
  {
    id: "discourse",
    label: "Discourse",
    question: "How does the reader encounter it?",
  },
  { id: "mind", label: "Mind", question: "What does each character believe?" },
  {
    id: "provenance",
    label: "Provenance",
    question: "Where did this claim come from?",
  },
  {
    id: "motif",
    label: "Motif",
    question: "Where do recurring things appear?",
  },
  { id: "pipeline", label: "Pipeline", question: "Where did the run stop?" },
];

export async function rpc<T>(
  method: string,
  params: Record<string, unknown> = {},
): Promise<T> {
  try {
    return await invoke<T>("rpc_call", { method, params });
  } catch (reason) {
    const raw = String(reason);
    try {
      const parsed = JSON.parse(raw) as {
        message?: string;
        data?: { cmne_code?: string; field_path?: string; cause?: string; next_action?: string };
      };
      throw new Error(
        `${parsed.data?.cmne_code ? `${parsed.data.cmne_code}: ` : ""}${parsed.data?.cause ?? parsed.message ?? raw}${parsed.data?.field_path ? ` (${parsed.data.field_path})` : ""}${parsed.data?.next_action ? ` Next: ${parsed.data.next_action}` : ""}`,
      );
    } catch (error) {
      if (error instanceof SyntaxError) throw new Error(raw);
      throw error;
    }
  }
}

export function shortId(id: string): string {
  return id.length > 19 ? `${id.slice(0, 12)}…` : id;
}
