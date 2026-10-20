import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ArrowLeftRight,
  BookOpen,
  ChevronDown,
  CircleHelp,
  Command,
  Download,
  GitBranch,
  Layers3,
  LockKeyhole,
  Menu,
  Plus,
  Play,
  RotateCcw,
  Pencil,
  Search,
  Split,
  TriangleAlert,
  X,
} from "./icons";
import { invoke } from "@tauri-apps/api/core";
import GraphCanvas from "./GraphCanvas";
import { LENSES, rpc, shortId } from "./api";
import type {
  Draft,
  DraftNode,
  Lens,
  ProjectSummary,
  RunResult,
  ViewGraph,
  ViewNode,
} from "./api";
import "./styles.css";

const CONDITION_LABELS: Record<string, string> = {
  C0: "Fact revelation",
  C1: "Belief revision",
  C2: "Modal revision",
  C3: "Conceptual revision",
};

function parseList(value: string): string[] {
  return value
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);
}
function listValue(value: unknown): string {
  return Array.isArray(value) ? value.join(", ") : "";
}

function Field({
  label,
  value,
  onChange,
  multiline = false,
  hint,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  multiline?: boolean;
  hint?: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {multiline ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={4}
        />
      ) : (
        <input value={value} onChange={(e) => onChange(e.target.value)} />
      )}
      {hint && <small>{hint}</small>}
    </label>
  );
}

function Sparkline({
  values,
  threshold,
}: {
  values: number[];
  threshold: number;
}) {
  const width = 570,
    height = 128,
    left = 34,
    top = 13,
    plotW = width - 48,
    plotH = height - 30;
  const points = values
    .map(
      (v, i) =>
        `${left + (i / Math.max(1, values.length - 1)) * plotW},${top + plotH - (v / 10000) * plotH}`,
    )
    .join(" ");
  const ty = top + plotH - (threshold / 10000) * plotH;
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="strain-chart"
      role="img"
      aria-label={`Strain over ${values.length} story events; threshold ${threshold / 100}%`}
    >
      {[0, 2500, 5000, 7500, 10000].map((v) => (
        <g key={v}>
          <line
            x1={left}
            x2={width - 12}
            y1={top + plotH - (v / 10000) * plotH}
            y2={top + plotH - (v / 10000) * plotH}
            className="chart-grid"
          />
          <text x={0} y={top + plotH - (v / 10000) * plotH + 4}>
            {v / 100}%
          </text>
        </g>
      ))}
      <line
        x1={left}
        x2={width - 12}
        y1={ty}
        y2={ty}
        className="chart-threshold"
      />
      <polyline points={points} className="chart-line" />
      {values.map((v, i) => (
        <circle
          key={i}
          cx={left + (i / Math.max(1, values.length - 1)) * plotW}
          cy={top + plotH - (v / 10000) * plotH}
          r="3.5"
          className="chart-dot"
        />
      ))}
    </svg>
  );
}

export default function App() {
  const [project, setProject] = useState<ProjectSummary | null>(null);
  const [branch, setBranch] = useState("main");
  const [lens, setLens] = useState<Lens>("story");
  const [graph, setGraph] = useState<ViewGraph | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pendingSource, setPendingSource] = useState<string | null>(null);
  const [outline, setOutline] = useState(false);
  const [run, setRun] = useState<RunResult | null>(null);
  const [strain, setStrain] = useState<number[]>([]);
  const [discourseCount, setDiscourseCount] = useState(0);
  const [storyTime, setStoryTime] = useState<number | null>(null);
  const [discourseTime, setDiscourseTime] = useState<number | null>(null);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [modal, setModal] = useState<
    "create" | "open" | "compare" | "help" | null
  >(null);
  const [pathInput, setPathInput] = useState("");
  const [nameInput, setNameInput] = useState("Untitled scene");
  const [comparison, setComparison] = useState<Record<string, unknown> | null>(
    null,
  );
  const [compareBranch, setCompareBranch] = useState("");
  const [trace, setTrace] = useState<Record<string, unknown> | null>(null);
  const saveQueue = useRef<Promise<unknown>>(Promise.resolve());
  const history = useRef<{ past: Draft[]; future: Draft[] }>({
    past: [],
    future: [],
  });
  const [historyDepth, setHistoryDepth] = useState({ past: 0, future: 0 });

  function resetHistory() {
    history.current = { past: [], future: [] };
    setHistoryDepth({ past: 0, future: 0 });
  }

  const activeNode = graph?.nodes.find((n) => n.id === selectedId) ?? null;
  const activeDraftNode = draft?.nodes.find((n) => n.id === selectedId) ?? null;
  const isEditable = lens === "story" || lens === "discourse";
  const key = project ? `${project.path}:${branch}:${lens}` : "";

  const refresh = useCallback(
    async (
      draftId?: string | null,
      targetLens?: Lens,
      targetBranch?: string,
      targetStoryTime?: number | null,
      targetDiscourseTime?: number | null,
    ) => {
      if (!project) return;
      const useLens = targetLens ?? lens,
        useBranch = targetBranch ?? branch;
      const nextGraph = await rpc<ViewGraph>("graph.get", {
        lens: useLens,
        branch_id: useBranch,
        draft_id: draftId === undefined ? draft?.id : draftId,
        sequence: targetStoryTime === undefined ? storyTime : targetStoryTime,
        discourse_index:
          targetDiscourseTime === undefined
            ? discourseTime
            : targetDiscourseTime,
      });
      setGraph(nextGraph);
      const series = await rpc<{ series: { strain_bp: number }[] }>(
        "strain.series",
        { branch_id: useBranch },
      );
      setStrain(series.series.map((point) => point.strain_bp));
    },
    [project, lens, branch, draft?.id, storyTime, discourseTime],
  );

  async function openProject(
    method: "project.open" | "project.create" | "project.sample",
    params: Record<string, unknown>,
  ): Promise<boolean> {
    setBusy(true);
    try {
      await saveQueue.current;
      const summary = await rpc<ProjectSummary>(method, params);
      localStorage.setItem("cmne:last-project", summary.path);
      setProject(summary);
      setBranch(summary.active_branch);
      setLens("story");
      setStoryTime(null);
      setDiscourseTime(null);
      setSelectedId(null);
      setRun(null);
      setModal(null);
      const recoveredId = localStorage.getItem(
        `cmne:draft:${summary.path}:${summary.active_branch}:story`,
      );
      let recoveredDraft: Draft | null = null;
      if (recoveredId) {
        try {
          recoveredDraft = await rpc<Draft>("draft.get", {
            draft_id: recoveredId,
          });
        } catch {
          localStorage.removeItem(
            `cmne:draft:${summary.path}:${summary.active_branch}:story`,
          );
        }
      }
      setDraft(recoveredDraft);
      resetHistory();
      const [nextGraph, series, lastRun, discourseEvents] = await Promise.all([
        rpc<ViewGraph>("graph.get", {
          lens: "story",
          branch_id: summary.active_branch,
          draft_id: recoveredDraft?.id,
        }),
        rpc<{ series: { strain_bp: number }[] }>("strain.series", {
          branch_id: summary.active_branch,
        }),
        rpc<RunResult | { status: string }>("run.status", {
          branch_id: summary.active_branch,
        }),
        rpc<unknown[]>("events.read", {
          branch_id: summary.active_branch,
          stream: "discourse",
        }),
      ]);
      setGraph(nextGraph);
      setStrain(series.series.map((point) => point.strain_bp));
      setDiscourseCount(discourseEvents.length);
      setRun("run_id" in lastRun ? lastRun : null);
      setNotice(
        recoveredDraft
          ? `Recovered ${recoveredDraft.nodes.length} draft node${recoveredDraft.nodes.length === 1 ? "" : "s"} in ${summary.name}.`
          : `Opened ${summary.name}`,
      );
      return true;
    } catch (error) {
      setNotice(String(error));
      return false;
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        await rpc("app.hello", { protocol_version: "1.0" });
        if (!mounted) return;
        const last = localStorage.getItem("cmne:last-project");
        if (last) {
          if (await openProject("project.open", { path: last })) return;
        }
        await openProject("project.sample", {});
      } catch (error) {
        if (mounted) setNotice(`Desktop bridge unavailable: ${String(error)}`);
      }
    })();
    return () => {
      mounted = false;
    };
    // Startup is intentionally a one-time action.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    function keys(event: KeyboardEvent) {
      const editing =
        event.target instanceof HTMLElement &&
        ["INPUT", "TEXTAREA", "SELECT"].includes(event.target.tagName);
      if (event.key === "Escape") {
        setPendingSource(null);
        setModal(null);
      }
      if (
        (event.metaKey || event.ctrlKey) &&
        event.key.toLowerCase() === "z" &&
        draft &&
        !modal
      ) {
        event.preventDefault();
        if (event.shiftKey) void redoDraft();
        else void undoDraft();
        return;
      }
      if (editing) return;
      if (event.altKey && /^[1-7]$/.test(event.key)) {
        event.preventDefault();
        void switchLens(LENSES[Number(event.key) - 1].id);
      }
      if (event.altKey && event.key.toLowerCase() === "o") {
        event.preventDefault();
        setOutline((v) => !v);
      }
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
        event.preventDefault();
        void sealDraft();
      }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        if (isEditable) void addNode();
      }
      if (event.key.toLowerCase() === "c" && activeNode)
        setPendingSource(activeNode.id);
      if (event.key === "[")
        setStoryTime((v) => Math.max(0, (v ?? strain.length) - 1));
      if (event.key === "]")
        setStoryTime((v) => Math.min(strain.length, (v ?? strain.length) + 1));
    }
    window.addEventListener("keydown", keys);
    return () => window.removeEventListener("keydown", keys);
  });

  useEffect(() => {
    if (project && graph)
      void refresh(undefined, lens, branch, storyTime, discourseTime).catch(
        (error) => setNotice(String(error)),
      );
    // Scrub changes reproject the graph.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storyTime, discourseTime]);

  async function switchLens(nextLens: Lens) {
    if (!project) return;
    await saveQueue.current;
    setLens(nextLens);
    setPendingSource(null);
    setTrace(null);
    const draftId = localStorage.getItem(
      `cmne:draft:${project.path}:${branch}:${nextLens}`,
    );
    let nextDraft: Draft | null = null;
    if (draftId && (nextLens === "story" || nextLens === "discourse")) {
      try {
        nextDraft = await rpc<Draft>("draft.get", { draft_id: draftId });
      } catch {
        localStorage.removeItem(
          `cmne:draft:${project.path}:${branch}:${nextLens}`,
        );
      }
    }
    setDraft(nextDraft);
    resetHistory();
    await refresh(nextDraft?.id ?? null, nextLens, branch);
  }

  async function switchBranch(nextBranch: string) {
    if (!project) return;
    await saveQueue.current;
    setBranch(nextBranch);
    setStoryTime(null);
    setDiscourseTime(null);
    setPendingSource(null);
    const draftId = localStorage.getItem(
      `cmne:draft:${project.path}:${nextBranch}:${lens}`,
    );
    let nextDraft: Draft | null = null;
    if (draftId && isEditable) {
      try {
        nextDraft = await rpc<Draft>("draft.get", { draft_id: draftId });
      } catch {
        /* no recovery */
      }
    }
    setDraft(nextDraft);
    resetHistory();
    await refresh(nextDraft?.id ?? null, lens, nextBranch, null, null);
    const acts = await rpc<unknown[]>("events.read", {
      branch_id: nextBranch,
      stream: "discourse",
    });
    setDiscourseCount(acts.length);
    const lastRun = await rpc<RunResult | { status: string }>("run.status", {
      branch_id: nextBranch,
    });
    setRun("run_id" in lastRun ? lastRun : null);
  }

  async function ensureDraft(): Promise<Draft> {
    if (draft && draft.branch_id === branch && draft.lens === lens)
      return draft;
    const created = await rpc<Draft>("draft.create", {
      branch_id: branch,
      lens,
    });
    localStorage.setItem(`cmne:draft:${key}`, created.id);
    setDraft(created);
    resetHistory();
    return created;
  }

  async function persistDraft(
    updated: Draft,
    record = true,
    previousDraft?: Draft,
  ) {
    const before = previousDraft ?? draft;
    if (record && before?.id === updated.id) {
      history.current.past = [...history.current.past, before].slice(-50);
      history.current.future = [];
      setHistoryDepth({ past: history.current.past.length, future: 0 });
    }
    setDraft(updated);
    setGraph((previous) => {
      if (
        !previous ||
        previous.lens !== updated.lens ||
        previous.branchId !== updated.branch_id
      )
        return previous;
      const sealedNodes = previous.nodes.filter((n) => n.state !== "draft");
      const sealedEdges = previous.edges.filter((e) => e.state !== "draft");
      const draftNodes: ViewNode[] = updated.nodes.map((n) => ({
        id: n.id,
        kind: updated.lens === "story" ? "story_event" : "discourse_act",
        title: n.title,
        fields: n.fields,
        state: "draft",
        lens: updated.lens,
        refs: { branchId: updated.branch_id },
        badges: [],
        textAlt: `Draft ${n.title}`,
      }));
      return {
        ...previous,
        nodes: [...sealedNodes, ...draftNodes],
        edges: [...sealedEdges, ...updated.edges],
      };
    });
    saveQueue.current = saveQueue.current
      .catch(() => undefined)
      .then(() => rpc<Draft>("draft.patch", { draft: updated }));
    try {
      await saveQueue.current;
    } catch (error) {
      setNotice(String(error));
    }
  }

  async function undoDraft() {
    if (!draft || !history.current.past.length) return;
    const previous = history.current.past.pop()!;
    history.current.future.push(draft);
    setHistoryDepth({
      past: history.current.past.length,
      future: history.current.future.length,
    });
    await persistDraft(previous, false);
    setNotice("Draft edit undone.");
  }

  async function redoDraft() {
    if (!draft || !history.current.future.length) return;
    const next = history.current.future.pop()!;
    history.current.past.push(draft);
    setHistoryDepth({
      past: history.current.past.length,
      future: history.current.future.length,
    });
    await persistDraft(next, false);
    setNotice("Draft edit restored.");
  }

  async function addNode() {
    if (!isEditable || !project) return;
    try {
      const current = await ensureDraft();
      const node: DraftNode = {
        id: `node_${crypto.randomUUID().replaceAll("-", "")}`,
        title: lens === "story" ? "New story event" : "New discourse act",
        fields:
          lens === "story"
            ? {
                kind: "action",
                description: "",
                actor_ids: [],
                observed_by: [],
                strain_bp: 0,
              }
            : {
                mode: "scene",
                text: "",
                focalizer:
                  (project.fixture.actors as { id: string }[])?.[0]?.id ?? "",
              },
      };
      await persistDraft(
        { ...current, nodes: [...current.nodes, node] },
        true,
        current,
      );
      setSelectedId(node.id);
      setNotice("Draft node added. Edit it in the inspector.");
    } catch (error) {
      setNotice(String(error));
    }
  }

  async function editDraftNode(
    patch: Partial<DraftNode>,
    fields?: Record<string, unknown>,
  ) {
    if (!draft || !activeDraftNode) return;
    const nodes = draft.nodes.map((n) =>
      n.id === activeDraftNode.id
        ? { ...n, ...patch, fields: { ...n.fields, ...fields } }
        : n,
    );
    await persistDraft({ ...draft, nodes });
  }

  async function connect(source: string, target: string) {
    if (!isEditable) return;
    try {
      const current = await ensureDraft();
      const kind = lens === "story" ? "causes" : "refs";
      const verdict = await rpc<{ accepted: boolean; reason: string }>(
        "graph.validate_connection",
        { branch_id: branch, lens, source, target, kind, draft: current },
      );
      if (!verdict.accepted) {
        setNotice(verdict.reason);
        setPendingSource(null);
        return;
      }
      const edge = {
        id: `edge_${crypto.randomUUID().replaceAll("-", "")}`,
        source,
        target,
        kind,
        state: "draft" as const,
      };
      await persistDraft(
        { ...current, edges: [...current.edges, edge] },
        true,
        current,
      );
      setNotice(`${kind} connection added.`);
      setPendingSource(null);
    } catch (error) {
      setNotice(String(error));
      setPendingSource(null);
    }
  }

  async function removeDraftNode() {
    if (!draft || !activeDraftNode) return;
    await persistDraft({
      ...draft,
      nodes: draft.nodes.filter((n) => n.id !== activeDraftNode.id),
      edges: draft.edges.filter(
        (e) =>
          e.source !== activeDraftNode.id && e.target !== activeDraftNode.id,
      ),
    });
    setSelectedId(null);
  }

  async function sealDraft() {
    if (!draft || !draft.nodes.length) {
      setNotice("There are no draft nodes to seal.");
      return;
    }
    setBusy(true);
    try {
      await saveQueue.current;
      await rpc("draft.patch", { draft });
      const preview = await rpc<{
        accepted: boolean;
        errors: { message: string; field_path: string }[];
      }>("draft.compile_preview", { draft_id: draft.id });
      if (!preview.accepted) {
        setNotice(
          preview.errors
            .map((e) => `${e.field_path}: ${e.message}`)
            .join(" · "),
        );
        return;
      }
      const result = await rpc<{
        accepted: boolean;
        errors: { message: string }[];
        emitted_events: unknown[];
      }>("draft.seal", { draft_id: draft.id });
      if (!result.accepted) {
        setNotice(result.errors.map((e) => e.message).join(" · "));
        return;
      }
      localStorage.removeItem(`cmne:draft:${key}`);
      setDraft(null);
      resetHistory();
      setSelectedId(null);
      await refresh(null);
      if (lens === "discourse")
        setDiscourseCount((v) => v + result.emitted_events.length);
      setNotice(
        `${result.emitted_events.length} event${result.emitted_events.length === 1 ? "" : "s"} sealed to ${branch}.`,
      );
    } catch (error) {
      setNotice(String(error));
    } finally {
      setBusy(false);
    }
  }

  async function forkFrom(node: ViewNode) {
    if (node.state !== "sealed" || !node.refs.sequence) return;
    const name = window.prompt("Name this branch", `From ${node.title}`);
    if (name === null) return;
    try {
      const fork = await rpc<{ branch_id: string; draft_id?: string }>(
        "branch.fork",
        {
          branch_id: branch,
          sequence: node.refs.sequence - 1,
          name: name || `From ${node.title}`,
        },
      );
      const branches = await rpc<ProjectSummary["branches"]>("branch.list");
      setProject(project ? { ...project, branches } : null);
      if (fork.draft_id)
        localStorage.setItem(
          `cmne:draft:${project?.path}:${fork.branch_id}:story`,
          fork.draft_id,
        );
      setLens("story");
      setBranch(fork.branch_id);
      setStoryTime(null);
      setDiscourseTime(null);
      const nextDraft = fork.draft_id
        ? await rpc<Draft>("draft.get", { draft_id: fork.draft_id })
        : null;
      setDraft(nextDraft);
      resetHistory();
      await refresh(nextDraft?.id ?? null, "story", fork.branch_id, null, null);
      setRun(null);
      const acts = await rpc<unknown[]>("events.read", {
        branch_id: fork.branch_id,
        stream: "discourse",
      });
      setDiscourseCount(acts.length);
      setNotice(`Forked at ${node.title}. Edit the new branch, then seal.`);
    } catch (error) {
      setNotice(String(error));
    }
  }

  async function startRun() {
    if (draft?.nodes.length) {
      setNotice("Seal the draft before running. Runs read sealed events only.");
      return;
    }
    setBusy(true);
    try {
      const result = await rpc<RunResult>("run.start", {
        branch_id: branch,
        conditions: [
          project?.branches.find((item) => item.branch_id === branch)
            ?.condition ?? "C3",
        ],
      });
      setRun(result);
      setLens("pipeline");
      setDraft(null);
      resetHistory();
      await refresh(null, "pipeline");
      setNotice(
        result.status === "passed"
          ? "Run complete. Grounding check passed."
          : "Run complete with findings.",
      );
    } catch (error) {
      setNotice(String(error));
    } finally {
      setBusy(false);
    }
  }

  async function startAllRuns() {
    if (draft?.nodes.length) {
      setNotice("Seal the draft before running. Runs read sealed events only.");
      return;
    }
    setBusy(true);
    try {
      const result = await rpc<{ runs: RunResult[]; status: string }>(
        "run.start",
        { conditions: ["C0", "C1", "C2", "C3"] },
      );
      setRun(result.runs.find((item) => item.branch_id === branch) ?? null);
      setLens("pipeline");
      setDraft(null);
      resetHistory();
      await refresh(null, "pipeline");
      setNotice(
        result.status === "passed"
          ? "All four condition runs passed. Select a branch to read its passage."
          : "Condition runs completed with findings. Review the pipeline.",
      );
    } catch (error) {
      setNotice(String(error));
    } finally {
      setBusy(false);
    }
  }

  async function exportReport() {
    try {
      const result = await rpc<{ path: string }>("export.report", {
        branch_id: branch,
      });
      setNotice(`Report saved to ${result.path}`);
    } catch (error) {
      setNotice(String(error));
    }
  }

  async function askWhy() {
    if (!activeNode) return;
    try {
      setTrace(
        await rpc<Record<string, unknown>>("trace.query", {
          branch_id: branch,
          node_id: activeNode.id,
        }),
      );
    } catch (error) {
      setNotice(String(error));
    }
  }

  async function doCompare() {
    try {
      const result = await rpc<Record<string, unknown>>("branch.compare", {
        left: branch,
        right: compareBranch,
      });
      setComparison(result);
    } catch (error) {
      setNotice(String(error));
    }
  }

  const storyCount = useMemo(
    () =>
      graph?.nodes.filter(
        (n) => n.kind === "story_event" && n.state === "sealed",
      ).length ?? strain.length,
    [graph, strain],
  );
  const title = LENSES.find((item) => item.id === lens);
  const actorIds = (project?.fixture.actors ?? []) as {
    id: string;
    name: string;
  }[];
  const threshold = Number(project?.contract.strain_threshold_bp ?? 6500);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand-mark">
          <Layers3 size={22} strokeWidth={2.2} />
        </div>
        <div className="brand">
          <strong>CMNE</strong>
          <span>NARRATIVE WORKBENCH</span>
        </div>
        <div className="top-separator" />
        <button
          className="project-switch"
          onClick={() => setModal("open")}
          title="Open another project"
        >
          <span className="project-kicker">PROJECT</span>
          <span>{project?.name ?? "Opening sample…"}</span>
          <ChevronDown size={15} />
        </button>
        <div className="spacer" />
        <span className={`sidecar-indicator ${project ? "" : "offline"}`}>
          <i /> {project ? "LOCAL SIDECAR" : "CONNECTING"}
        </span>
        <button
          className="top-icon"
          title="Glossary and shortcuts"
          onClick={() => setModal("help")}
        >
          <CircleHelp size={18} />
        </button>
      </header>

      <div className="workspace">
        <aside className="sidebar">
          <div className="side-section-heading">
            <span>WORKSPACE</span>
            <Menu size={15} />
          </div>
          <div className="side-project">
            <div className="side-project-icon">
              <BookOpen size={22} />
            </div>
            <div>
              <strong>{project?.name ?? "No project"}</strong>
              <small>
                {project?.fixture.name
                  ? String(project.fixture.name)
                  : "Local narrative project"}
              </small>
            </div>
          </div>
          <div className="side-label">LENSES</div>
          <nav className="lens-nav" aria-label="Graph lenses">
            {LENSES.map((item, i) => (
              <button
                key={item.id}
                className={lens === item.id ? "active" : ""}
                onClick={() => void switchLens(item.id)}
              >
                <span className="lens-number">0{i + 1}</span>
                <span>{item.label}</span>
                {lens === item.id && <span className="lens-dot" />}
              </button>
            ))}
          </nav>
          <div className="side-divider" />
          <div className="side-label side-label-row">
            <span>BRANCHES</span>
            <button
              className="bare-icon"
              onClick={() => activeNode && void forkFrom(activeNode)}
              title="Fork from selected event"
            >
              <Plus size={15} />
            </button>
          </div>
          <div className="branches">
            {project?.branches.map((item) => (
              <button
                key={item.branch_id}
                className={branch === item.branch_id ? "active" : ""}
                onClick={() => void switchBranch(item.branch_id)}
              >
                <GitBranch size={15} />
                <span>{item.name ?? item.branch_id}</span>
                {branch === item.branch_id && (
                  <span className="branch-active-dot" />
                )}
              </button>
            ))}
          </div>
          <button
            className="side-compare"
            onClick={() => {
              setCompareBranch(
                project?.branches.find((b) => b.branch_id !== branch)
                  ?.branch_id ?? "",
              );
              setComparison(null);
              setModal("compare");
            }}
          >
            <ArrowLeftRight size={15} /> Compare branches
          </button>
          <div className="sidebar-bottom">
            <div className="sidebar-tip">
              <strong>THE IDEA</strong>
              <p>
                A moment can change the meaning of what came before. Follow that
                change through story, mind, and telling.
              </p>
            </div>
            <span>CMNE 0.1.0 · LOCAL FIRST</span>
          </div>
        </aside>

        <main className="main">
          <div className="main-heading">
            <div>
              <div className="eyebrow">
                GRAPH WORKBENCH <span>/</span> {title?.label.toUpperCase()}
              </div>
              <h1>
                {title?.label} <span>lens</span>
              </h1>
              <p>{title?.question}</p>
            </div>
            <div className="main-actions">
              {isEditable && (
                <button className="secondary" onClick={() => void addNode()}>
                  <Plus size={16} /> Add {lens === "story" ? "event" : "act"}
                </button>
              )}
              {isEditable && (
                <button
                  className="secondary"
                  onClick={() => void sealDraft()}
                  disabled={!draft?.nodes.length || busy}
                >
                  <LockKeyhole size={16} /> Seal draft
                </button>
              )}
              <button
                className="primary"
                onClick={() => void startRun()}
                disabled={!project || busy}
              >
                <Play size={16} fill="currentColor" /> Run scene
              </button>
              {project?.branches.filter((item) => item.condition).length ===
                4 && (
                <button
                  className="secondary"
                  onClick={() => void startAllRuns()}
                  disabled={busy}
                  title="Run C0, C1, C2, and C3 on their branches"
                >
                  <Activity size={16} /> Run C0–C3
                </button>
              )}
            </div>
          </div>
          <div className="context-row">
            <span>
              <GitBranch size={14} />{" "}
              {project?.branches.find((b) => b.branch_id === branch)?.name ??
                branch}
            </span>
            <span className="context-divider">/</span>
            <span>{graph?.nodes.length ?? 0} visible nodes</span>
            {draft && (
              <span className="draft-pill">
                <PencilIcon /> Unsealed draft · {draft.nodes.length} nodes
              </span>
            )}
            {draft && (
              <>
                <button
                  className="view-toggle"
                  disabled={!historyDepth.past}
                  onClick={() => void undoDraft()}
                  title="Undo draft edit (Ctrl/Cmd+Z)"
                >
                  ↶ Undo
                </button>
                <button
                  className="view-toggle"
                  disabled={!historyDepth.future}
                  onClick={() => void redoDraft()}
                  title="Redo draft edit (Ctrl/Cmd+Shift+Z)"
                >
                  ↷ Redo
                </button>
              </>
            )}
            <div className="spacer" />
            <button
              className={outline ? "view-toggle active" : "view-toggle"}
              onClick={() => setOutline(!outline)}
            >
              <Menu size={15} /> Outline
            </button>
            <button
              className={!outline ? "view-toggle active" : "view-toggle"}
              onClick={() => setOutline(false)}
            >
              <Split size={15} /> Canvas
            </button>
          </div>
          <div className="canvas-region">
            {graph ? (
              outline ? (
                <div className="outline-view">
                  <div className="outline-heading">
                    <h2>{title?.label} outline</h2>
                    <p>
                      Text alternative to the canvas. Select a row to inspect or
                      connect nodes.
                    </p>
                  </div>
                  <table>
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Kind</th>
                        <th>State</th>
                        <th>Title</th>
                        <th>Relations</th>
                      </tr>
                    </thead>
                    <tbody>
                      {graph.nodes.map((node) => (
                        <tr
                          key={node.id}
                          className={selectedId === node.id ? "selected" : ""}
                          onClick={() =>
                            pendingSource
                              ? void connect(pendingSource, node.id)
                              : setSelectedId(node.id)
                          }
                          tabIndex={0}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") setSelectedId(node.id);
                          }}
                        >
                          <td>{shortId(node.id)}</td>
                          <td>{node.kind.replace("_", " ")}</td>
                          <td>{node.state}</td>
                          <td>{node.title}</td>
                          <td>
                            {graph.edges
                              .filter(
                                (e) =>
                                  e.source === node.id || e.target === node.id,
                              )
                              .map((e) => e.kind)
                              .join(", ") || "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {!graph.nodes.length && (
                    <p className="empty-outline">No nodes in this lens.</p>
                  )}
                </div>
              ) : (
                <GraphCanvas
                  graph={graph}
                  selectedId={selectedId}
                  onSelect={setSelectedId}
                  onAdd={() => void addNode()}
                  onConnect={(a, b) => void connect(a, b)}
                  pendingSource={pendingSource}
                  lens={lens}
                />
              )
            ) : (
              <div className="loading-graph">
                {busy ? "Opening project…" : "Open a project to begin."}
              </div>
            )}
          </div>
          <div className="scrubber">
            <div>
              <span className="scrubber-label">STORY TIME</span>
              <input
                type="range"
                min={0}
                max={Math.max(1, strain.length)}
                value={storyTime ?? strain.length}
                onChange={(e) => setStoryTime(Number(e.target.value))}
                disabled={!strain.length}
              />
              <strong>
                {storyTime ?? strain.length} / {strain.length}
              </strong>
            </div>
            <div>
              <span className="scrubber-label">DISCOURSE</span>
              <input
                type="range"
                min={0}
                max={Math.max(1, discourseCount)}
                value={discourseTime ?? discourseCount}
                onChange={(e) => setDiscourseTime(Number(e.target.value))}
              />
              <strong>{discourseTime ?? "All"}</strong>
            </div>
            <button
              title="Reset time scrubbers"
              onClick={() => {
                setStoryTime(null);
                setDiscourseTime(null);
              }}
            >
              <RotateCcw size={15} />
            </button>
          </div>
          <section className="bottom-dock">
            <div className="dock-head">
              <div>
                <span className="eyebrow">RUN ANALYSIS</span>
                <h2>Strain &amp; progression</h2>
              </div>
              <div className="dock-actions">
                <span className="legend-line" /> Mara's strain{" "}
                <span className="legend-threshold" /> Crisis threshold
              </div>
            </div>
            <div className="dock-content">
              <div className="chart-panel">
                <Sparkline values={strain} threshold={threshold} />
                <div className="chart-caption">
                  <span>
                    STORY SEQUENCE{" "}
                    <strong>
                      01 — {String(strain.length).padStart(2, "0")}
                    </strong>
                  </span>
                  <span>
                    THRESHOLD <strong>{threshold / 100}%</strong>
                  </span>
                </div>
              </div>
              <div className="run-summary">
                <span className="eyebrow">
                  LATEST RUN{" "}
                  {run?.conditions[0]
                    ? `· ${run.conditions[0]} ${CONDITION_LABELS[run.conditions[0]] ?? ""}`
                    : ""}
                </span>
                {run ? (
                  <>
                    <div className={`run-status status-${run.status}`}>
                      {run.status === "passed" ? "✓" : "!"}{" "}
                      {run.status.toUpperCase()}
                    </div>
                    <p>
                      {run.findings.length
                        ? `${run.findings.length} finding${run.findings.length === 1 ? "" : "s"} need review.`
                        : "All deterministic checks passed."}
                    </p>
                    <button onClick={() => void exportReport()}>
                      <Download size={14} /> Export report
                    </button>
                  </>
                ) : (
                  <>
                    <div className="run-status idle">○ NOT RUN</div>
                    <p>
                      Run the scene to build a packet and inspect its passage.
                    </p>
                  </>
                )}
              </div>
            </div>
            {run && (
              <details className="passage-details">
                <summary>
                  Read generated passage{" "}
                  <span>{run.prose.trim().split(/\s+/).length} words</span>
                </summary>
                <article>
                  {run.prose.split("\n\n").map((p, i) => (
                    <p key={i}>{p}</p>
                  ))}
                </article>
              </details>
            )}
            {run?.findings.map((finding, i) => (
              <div className="finding-row" key={i}>
                <TriangleAlert size={15} /> <strong>{finding.code}</strong>
                <span>{finding.message}</span>
              </div>
            ))}
          </section>
        </main>

        <aside className="inspector">
          <div className="inspector-head">
            <div>
              <span className="eyebrow">INSPECTOR</span>
              <h2>{activeNode ? "Node details" : "No selection"}</h2>
            </div>
            {activeNode && (
              <button
                className="bare-icon"
                onClick={() => {
                  setSelectedId(null);
                  setTrace(null);
                }}
                aria-label="Clear selection"
              >
                <X size={18} />
              </button>
            )}
          </div>
          {activeNode ? (
            <div className="inspector-body">
              <div className={`inspector-card state-${activeNode.state}`}>
                <div className="inspector-card-top">
                  <span>{activeNode.kind.replace("_", " ").toUpperCase()}</span>
                  <span>
                    {activeNode.state === "sealed" ? (
                      <LockKeyhole size={14} />
                    ) : (
                      <PencilIcon />
                    )}{" "}
                    {activeNode.state.toUpperCase()}
                  </span>
                </div>
                <h3>{activeNode.title}</h3>
                <code>{shortId(activeNode.id)}</code>
              </div>
              {activeDraftNode ? (
                <div className="inspector-form">
                  <div className="inspector-section-title">EDIT DRAFT</div>
                  <Field
                    label="Title"
                    value={activeDraftNode.title}
                    onChange={(v) => void editDraftNode({ title: v })}
                  />
                  {lens === "story" ? (
                    <>
                      <label className="field">
                        <span>Event kind</span>
                        <select
                          value={String(
                            activeDraftNode.fields.kind ?? "action",
                          )}
                          onChange={(e) =>
                            void editDraftNode({}, { kind: e.target.value })
                          }
                        >
                          {[
                            "action",
                            "observation",
                            "utterance",
                            "recollection",
                            "decision",
                            "revision",
                            "crisis",
                          ].map((kind) => (
                            <option key={kind}>{kind}</option>
                          ))}
                        </select>
                      </label>
                      <Field
                        label="Description"
                        value={String(activeDraftNode.fields.description ?? "")}
                        multiline
                        onChange={(v) =>
                          void editDraftNode({}, { description: v })
                        }
                      />
                      <Field
                        label="Actors"
                        value={listValue(activeDraftNode.fields.actor_ids)}
                        onChange={(v) =>
                          void editDraftNode({}, { actor_ids: parseList(v) })
                        }
                        hint={`IDs: ${actorIds.map((a) => a.id).join(", ")}`}
                      />
                      <Field
                        label="Observed by"
                        value={listValue(activeDraftNode.fields.observed_by)}
                        onChange={(v) =>
                          void editDraftNode({}, { observed_by: parseList(v) })
                        }
                      />
                      <label className="field">
                        <span>Access path</span>
                        <select
                          value={String(
                            activeDraftNode.fields.access_path ?? "",
                          )}
                          onChange={(e) =>
                            void editDraftNode(
                              {},
                              { access_path: e.target.value },
                            )
                          }
                        >
                          <option value="">None</option>
                          <option value="perception">Perception</option>
                          <option value="testimony">Testimony</option>
                          <option value="memory">Memory</option>
                        </select>
                      </label>
                      <label className="field">
                        <span>
                          Strain ·{" "}
                          {Number(activeDraftNode.fields.strain_bp ?? 0) / 100}%
                        </span>
                        <input
                          type="range"
                          min="0"
                          max="10000"
                          step="100"
                          value={Number(activeDraftNode.fields.strain_bp ?? 0)}
                          onChange={(e) =>
                            void editDraftNode(
                              {},
                              { strain_bp: Number(e.target.value) },
                            )
                          }
                        />
                      </label>
                    </>
                  ) : (
                    <>
                      <label className="field">
                        <span>Mode</span>
                        <select
                          value={String(activeDraftNode.fields.mode ?? "scene")}
                          onChange={(e) =>
                            void editDraftNode({}, { mode: e.target.value })
                          }
                        >
                          {[
                            "scene",
                            "summary",
                            "ellipsis",
                            "pause",
                            "memory",
                            "repetition",
                          ].map((mode) => (
                            <option key={mode}>{mode}</option>
                          ))}
                        </select>
                      </label>
                      <Field
                        label="Passage text"
                        value={String(activeDraftNode.fields.text ?? "")}
                        multiline
                        onChange={(v) => void editDraftNode({}, { text: v })}
                      />
                      <label className="field">
                        <span>Focalizer</span>
                        <select
                          value={String(activeDraftNode.fields.focalizer ?? "")}
                          onChange={(e) =>
                            void editDraftNode(
                              {},
                              { focalizer: e.target.value },
                            )
                          }
                        >
                          <option value="">Narrator</option>
                          {actorIds.map((a) => (
                            <option key={a.id} value={a.id}>
                              {a.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <Field
                        label="Reveal claims"
                        value={listValue(activeDraftNode.fields.reveal)}
                        onChange={(v) =>
                          void editDraftNode({}, { reveal: parseList(v) })
                        }
                      />
                      <Field
                        label="Withhold claims"
                        value={listValue(activeDraftNode.fields.withhold)}
                        onChange={(v) =>
                          void editDraftNode({}, { withhold: parseList(v) })
                        }
                      />
                    </>
                  )}
                  <div className="inspector-buttons">
                    <button
                      className="secondary"
                      onClick={() => setPendingSource(activeNode.id)}
                    >
                      <GitBranch size={14} /> Connect from
                    </button>
                    <button
                      className="danger-quiet"
                      onClick={() => void removeDraftNode()}
                    >
                      Delete draft
                    </button>
                  </div>
                </div>
              ) : (
                <div className="read-fields">
                  <div className="inspector-section-title">
                    CANONICAL FIELDS
                  </div>
                  {Object.entries(activeNode.fields)
                    .filter(([k]) => !["description", "text"].includes(k))
                    .slice(0, 10)
                    .map(([k, v]) => (
                      <div className="read-field" key={k}>
                        <span>{k.replaceAll("_", " ")}</span>
                        <strong>
                          {Array.isArray(v)
                            ? v.join(", ") || "—"
                            : typeof v === "object"
                              ? JSON.stringify(v).slice(0, 100)
                              : String(v || "—")}
                        </strong>
                      </div>
                    ))}
                  {Boolean(
                    activeNode.fields.description || activeNode.fields.text,
                  ) && (
                    <p className="node-description">
                      {String(
                        activeNode.fields.description || activeNode.fields.text,
                      )}
                    </p>
                  )}
                </div>
              )}
              <div className="inspector-section-title">ACTIONS</div>
              <div className="inspector-actions">
                <button onClick={() => void askWhy()}>
                  <Search size={15} /> Why is this here?
                </button>
                {activeNode.state === "sealed" &&
                  activeNode.kind === "story_event" && (
                    <button onClick={() => void forkFrom(activeNode)}>
                      <GitBranch size={15} /> Fork from here
                    </button>
                  )}
                {activeNode.state === "sealed" && (
                  <div className="sealed-note">
                    <LockKeyhole size={14} /> Sealed events cannot be edited.
                    Fork to explore a change.
                  </div>
                )}
              </div>
              {trace && (
                <div className="trace-card">
                  <strong>PROVENANCE TRACE</strong>
                  <pre>{JSON.stringify(trace, null, 2)}</pre>
                </div>
              )}
            </div>
          ) : (
            <div className="inspector-empty">
              <div className="empty-icon">
                <Search size={25} />
              </div>
              <h3>Explore the graph</h3>
              <p>
                Select a node to inspect its state, provenance, and available
                actions.
              </p>
              <div className="shortcut">
                <Command size={14} /> Click a node or use the outline view
              </div>
            </div>
          )}
          <div className="inspector-footer">
            <Activity size={14} />
            <span>Projections derived from sealed events</span>
          </div>
        </aside>
      </div>

      {notice && (
        <div className="toast" role="status">
          <span>{notice}</span>
          <button
            onClick={() => setNotice("")}
            aria-label="Dismiss notification"
          >
            <X size={15} />
          </button>
        </div>
      )}

      {modal && (
        <div
          className="modal-backdrop"
          role="presentation"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setModal(null);
          }}
        >
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label={modal}
          >
            <button
              className="modal-close"
              onClick={() => setModal(null)}
              aria-label="Close"
            >
              <X size={18} />
            </button>
            {modal === "open" || modal === "create" ? (
              <>
                <span className="eyebrow">PROJECT LIBRARY</span>
                <h2>
                  {modal === "create"
                    ? "Create a scene project"
                    : "Open a project"}
                </h2>
                <p>
                  Projects live in a folder you choose. Story, discourse,
                  drafts, runs, and reports stay on this computer.
                </p>
                <Field
                  label="Folder path"
                  value={pathInput}
                  onChange={setPathInput}
                  hint="Enter an absolute path to an existing CMNE project, or a new folder for a new project."
                />
                {modal === "create" && (
                  <Field
                    label="Project name"
                    value={nameInput}
                    onChange={setNameInput}
                  />
                )}
                <div className="modal-actions">
                  <button
                    className="secondary"
                    onClick={() => {
                      setModal(modal === "open" ? "create" : "open");
                    }}
                  >
                    {modal === "open" ? "Create new" : "Open existing"}
                  </button>
                  <button
                    className="primary"
                    disabled={!pathInput || busy}
                    onClick={() =>
                      void openProject(
                        modal === "open" ? "project.open" : "project.create",
                        { path: pathInput, name: nameInput },
                      )
                    }
                  >
                    {modal === "open" ? "Open project" : "Create project"}
                  </button>
                </div>
                <button
                  className="sample-link"
                  onClick={() => void openProject("project.sample", {})}
                >
                  Open bundled Mara and Len sample →
                </button>
              </>
            ) : modal === "compare" ? (
              <>
                <span className="eyebrow">BRANCH ANALYSIS</span>
                <h2>Compare branches</h2>
                <p>
                  Find the first changed story event and compare projected
                  states.
                </p>
                <label className="field">
                  <span>Compare {branch} with</span>
                  <select
                    value={compareBranch}
                    onChange={(e) => setCompareBranch(e.target.value)}
                  >
                    {project?.branches
                      .filter((b) => b.branch_id !== branch)
                      .map((b) => (
                        <option key={b.branch_id} value={b.branch_id}>
                          {b.name ?? b.branch_id}
                        </option>
                      ))}
                  </select>
                </label>
                <button
                  className="primary"
                  disabled={!compareBranch}
                  onClick={() => void doCompare()}
                >
                  Compare
                </button>
                {comparison && (
                  <div className="comparison-result">
                    <strong>
                      Shared prefix: {String(comparison.shared_prefix)} events
                    </strong>
                    <p>
                      First difference:{" "}
                      {String(
                        comparison.first_diverging_sequence ?? "No difference",
                      )}
                    </p>
                    <p>
                      Left only: {String(comparison.left_only)} · Right only:{" "}
                      {String(comparison.right_only)}
                    </p>
                  </div>
                )}
              </>
            ) : (
              <>
                <span className="eyebrow">WORKBENCH GUIDE</span>
                <h2>Read the graph</h2>
                <p>
                  Shape identifies a kind of thing. A thick solid border and
                  lock mean sealed canon. A dashed border and pencil mean an
                  editable draft.
                </p>
                <div className="help-list">
                  <div>
                    <strong>Story</strong>
                    <span>What happened, in chronological order.</span>
                  </div>
                  <div>
                    <strong>Discourse</strong>
                    <span>How and when those events reach the reader.</span>
                  </div>
                  <div>
                    <strong>Mind</strong>
                    <span>
                      What each actor believes and how meanings change.
                    </span>
                  </div>
                  <div>
                    <strong>Fork</strong>
                    <span>
                      Try an alternate continuation from a sealed event.
                    </span>
                  </div>
                </div>
                <div className="help-keys">
                  Alt+1–7 switch lens · Alt+O outline · ⌘/Ctrl+K add ·
                  ⌘/Ctrl+Enter seal · C connect
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function PencilIcon() {
  return <Pencil size={14} />;
}
