# SRS-033 implementation status

| Field | Value |
|---|---|
| Date | 2026-10-21 |
| Scope | Current repository implementation, compared with the SRS-033 v0.2 design baseline |
| Status | Working local foundation; revised Milestones 5 and 8 pass local software gates, while full release and human sign-off remain open |

This is the implementation record for the design package. The SRS requirements, acceptance criteria, scenarios, diagrams, and proposed module layouts remain **targets** unless a row below explicitly describes delivered code. “Implemented” here describes the available behavior; it does not mean that every linked SRS acceptance criterion has passed. The package review's 100/100 is a score for the *written specification*, not the application. The dated [codebase review](SRS-033-Codebase-Review-2026-10-21.md) scores the software separately.

## Milestone 0/1 checkpoint

The Milestone 0 baseline includes [ADR-001–ADR-013](adr/ADR-001-sidecar-transport.md), `tests/acceptance_map.json`, `scripts/check_acceptance.py`, and `.github/workflows/ci.yml`. The inventory expands to 272 IDs (167 REQ, 40 GUI, 42 AC, 23 GAC): **32 passed, 8 partial, 232 planned**. This conservative status reflects the complete acceptance wording, not only narrower unit tests. CI is configured for Python, frontend, docs, and standard-library line coverage on macOS/Linux/Windows, plus Rust and packaged sidecar smoke on macOS. It has not yet run on GitHub from a clean checkout.

The Milestone 1 delivery adds typed Python boundary contracts, exported JSON Schema and TypeScript types, a checked and published error catalog, integer basis-point helper, safe JSON import, lock-aware read-only project opens and explicit stale-lock clearing. A same-stream command validates every payload before one atomic file replacement. Fixture and contract replacement recheck sealed events and preconditions before writing. A failed project switch retains the previous open project and writer lock. Existing sealed lines remain byte-identical on append/fork; corrupt event lines are named; full replay verifies and repairs snapshot caches. The shipped event schema and reducer are version 2. A real version-1 story/discourse file up-casts `source_kind: authored` in memory, then accepts new version-2 events without changing the old line. Project metadata remains format version 1.

Milestone 2 now computes integer strain from five weighted components, gates crisis on accessible evidence/commitment/repair budget, offers seven revision options, preserves v1/v2 interpretations, answers five provenance trace forms, compares state transitions, and derives a motif ledger. Milestone 3 now records discourse timing and reader before/after state in a focal-access packet; its deterministic checker annotates sentences and flags selected private-cognition, entity, causal, early-disclosure, forced-resolution, and voice violations. Rejected candidates and repair-first layers are saved. These are **selected deterministic rules**, not a general semantic grounding proof.

Milestone 5 now has frozen analysis plans and linked amendments, three distinct offline composition variants per condition, a randomized public set with plain text and accessible HTML, a private key stored outside the public export, atomic cited-span response import, and a report with agreement, effect-size intervals, rejection counts, contrary outcomes, and null alternatives. Layer A/B structural diagnostics and seven saved controlled ablation passages include packet/text hashes and checker findings; rejected passages remain visible. Milestone 6 exposes the study workflow through CLI, JSON-RPC, and a desktop panel, and adds validated fixture/contract JSON editors. Scene runs can execute in a background sidecar thread with progress polling and cancellation between conditions. The desktop remains responsive to committed-state reads during a run. Milestone 8 produces a deterministic, hashed generalization review packet with C0–C3 metrics, ablation results, effects, and a pending-human-review marker.

The revised Milestone 5 and 8 **local software** gates pass. Their human evaluation and generalization decision requirements move to Milestone 9; no literary or release outcome is asserted. Milestone 0 remains open pending clean-checkout cross-OS CI. Milestone 1 remains open pending complete INV-01–INV-18 evidence, cross-OS vectors (AC-27), the full import matrix (AC-32), and packaged GUI recovery (AC-38). Milestone 2 now has nine separate sealed-history fixtures with checked projections; deeper provenance/property evidence and complete AC coverage remain open. Milestone 3 needs adversarial grounding and full telling-plan semantics. Milestone 6 needs complete GUI authoring, keyboard/table parity, accessibility, performance, and packaged end-to-end evidence. Milestone 7 needs full automated release evidence. The current architecture retains JSON/NDJSON and SVG; ADR-002/003 document these choices.

## What runs now

| Area | Delivered behavior and source | Limit |
|---|---|---|
| Desktop | Tauri 2 Rust shell in `app/src-tauri/`; React 19, TypeScript, and Vite in `app/src/`; Rust relays allowlisted JSON-RPC 2.0 to Python. `app.hello` checks protocol major version; after child failure, the bridge retries only stateless validation calls and never replays an uncertain project mutation. Background run polling, cancellation between conditions, and study controls are available. | Progress is coarse by condition; full packaged GUI, keyboard, accessibility, and performance gates remain open. A failed stateful call requires reopening and inspecting the project. |
| Distribution | `scripts/prepare_sidecar.py` makes a development wrapper or PyInstaller executable for Tauri `externalBin`; an unsigned macOS `.app` bundle has been built. | Windows/Linux packages, signing, installation, and a packaged GUI smoke test have not been verified. |
| Project and kernel | `core.py`, `machines.py`, `formula.py`, `contracts.py`, `project.py`, and `upcast.py` validate typed shapes and selected invariants; evaluate bounded formulas; write hashed NDJSON atomic batches; replay six projections; compute weighted strain/crisis and versioned revisions; and save packets, snapshots, and runs. Nine separate golden histories check key projection outcomes. | No complete formal semantics, Pydantic layer, portable provenance graph export, or cross-platform vector results. Version-1-to-2 up-cast is implemented without rewriting stored bytes. |
| Authoring | Seven lenses (Fixture, Story, Discourse, Mind, Provenance, Motif, Pipeline), fixture/contract JSON editors with immediate prose-bound feedback, SVG graph, inspector, outline node/link tables, connection validation, story/discourse drafts, preview/seal, fork from sealed events, basic branch comparison, scrubber, four-condition strain chart, and trace details. Drafts persist on disk and can be recovered; undo/redo is in memory (50 steps). | Mind/Motif and concept/rule structures are chiefly views, not complete graph editors. No palette drag/drop, saved manual layout, minimap, semantic zoom, full overlay set, visual graph diff, or complete keyboard/table parity. |
| Sample and runs | `sample.py` seeds S01–S10, D01–D07, and C0–C3 after S01–S07. `run.start` can run synchronously or in a background worker; status polls and cancel stops between conditions. Three offline composition variants per condition support a 12-passage dry run. | The prose is deterministic authored expansion, not model-generated. Existing sample projects retain their stored contract until edited. No model adapter, cassette, call budget, or human-study result. |
| Checks and study | `prose.py` annotates sentences and checks selected grounding/voice patterns; `study.py` validates plans/responses, blinds passages, reports descriptive measures and intervals, saves seven controlled ablation passages with findings, and assembles a hashed generalization review packet. | Heuristic checks can miss paraphrases; sample ablations are controlled authored edits, not independent model generations. Human readers must judge literary quality in Milestone 9. |

## Current architecture and files

```text
React UI (app/src/App.tsx, GraphCanvas.tsx)
    -> Tauri invoke rpc_call (app/src-tauri/src/lib.rs)
    -> Python JSON-RPC dispatcher (src/cmne_sidecar/server.py)
    -> local kernel/project service (src/cmne/*.py)
    -> JSON metadata, fixture, contract, drafts, packets, runs;
       hashed NDJSON story/discourse/evaluation streams
```

The project format is `project.cmne.json`, `.cmne.lock`, `fixtures/active.json`, `contracts/active.json`, `branches/<id>/{story,discourse,evaluation}.ndjson`, `snapshots/<branch>.json`, `drafts/<id>.json`, `packets/<hash>.json`, `runs/<id>.json`, `exports/<id>.md`, `study/plans/`, `study/keys/`, `study/responses/`, `study/reports/`, and `exports/evaluation/<study-id>/public/`. The lock records PID, host, and start time; a second writer is refused while read-only opens remain available. Same-stream command batches replace the whole stream atomically, and a fork copies and verifies a shared prefix. This differs from the proposed YAML/Pydantic layout in IMPL-033.

The UI uses React state and custom SVG/HTML layout. React Flow, ELK, ECharts, Zustand, schema-generated forms, and the proposed testing/storybook stack in SRS-033-V and IMPL-033 are design options **not installed in this implementation**. The CLI is an expanded `argparse` entry point in `src/cmne/cli.py`, with machine-readable success/errors and study commands; Typer is not required by the current implementation.

The sidecar exposes project, fixture/contract, branch, event, graph, draft, scrub, strain, five trace forms, packet, run, individual export, and study methods. `draft.list` lets the workbench recover on-disk drafts after a lost local-storage pointer. `run.start` supports `async: true`; `run.status` returns a locked snapshot of completed condition count and saved runs, and `run.cancel` requests cancellation before the next condition. The RPC boundary rejects non-object requests and parameters. The RPC names are defined in `src/cmne_sidecar/server.py`; the Rust allowlist is in `app/src-tauri/src/lib.rs`.

## User workflow available today

1. Launch the app. On first use, it creates and opens the Mara/Len sample in `~/Documents/CMNE/Mara and Len`, or create/open a local project.
2. Inspect the seven lenses or outline, select story/discourse nodes, and scrub story or telling time. Add and seal story/discourse drafts. Fork a sealed story event to edit its suffix in a new branch.
3. Choose a seeded condition branch and run it, or run C0–C3 together. Inspect progress, saved status, passage, sentence findings, strain chart, and trace details. Export the selected branch's latest run to Markdown.
4. For a study dry run, save an analysis plan, generate 12 matched offline candidates, export a blinded set and private key, import structured responses, and read the descriptive report.

The workbench starts scene runs in a background sidecar worker. Its pipeline display reflects saved condition results as they complete; cancellation stops before the next condition. `branch.compare` reports transition and interpretation differences; it is not the designed visual diff overlay.

The v2 offline realizer expands only the unchanged Mara/Len seed. It does not rewrite sealed story or discourse events. If canon changes, it falls back to authored discourse text rather than reusing sample prose that could contradict the edited branch. Previously saved short runs remain in the project; rerun and export again to get the longer passage.

## Verification record

| Check | Result | Scope |
|---|---|---|
| `PYTHONPATH=src python3 -m unittest discover -s tests -q` | 88 tests passed locally | Store/replay plus project-switch/contract/post-commit errors, weighted crisis, revisions, provenance, packet/checker examples, study dry run, realized ablations, decision packet, CLI, and background cancellation. Selected checks, not the full AC/GAC gate. |
| `PYTHONPATH=src python3 scripts/coverage_report.py` | 89.4% Python executable-line coverage (2,785/3,116); [machine-readable report](../reports/coverage-2026-10-21.json) | Standard-library `trace`, not branch or frontend/Rust coverage. Core 97.6%, machines 97.3%, prose 93.5%, study 96.7%, project 89.4%, CLI 69.9%, sidecar 60.5%. |
| `mypy src --ignore-missing-imports --no-incremental`; `ruff check src scripts tests --select F,B,UP,SIM` | Both pass locally; configured in CI | Static typing covers 15 Python source files but allows dynamic JSON and does not prove runtime semantics. |
| `cd app && npm run build` | Passed | TypeScript check and Vite production build. |
| Rust 1.97.1 `cargo clippy --locked --all-targets -- -D warnings`; `cargo test --locked` with rustup first on `PATH` | Passed locally; one Rust recovery-policy test | Static check and small unit test, not a packaged GUI restart journey. The shell's default Rust 1.83 is too old. |
| `./build_app.sh --skip-install` | Passed locally on macOS | Unsigned `.app` assembled with the new bundled sidecar. |
| `python3 scripts/smoke_sidecar.py <bundle-sidecar>` | Passed locally outside the tool sandbox; [smoke record](../reports/packaged-sidecar-smoke-2026-10-21.json) | Packaged schema-2 handshake, create, disk-backed draft discovery, two-event batch, read, C0–C3 study generation/export, seven ablations, decision packet, and close. PyInstaller's semaphore requires normal macOS process permissions. |
| `python3 scripts/check_acceptance.py`; `python3 scripts/check_error_catalog.py`; `python3 scripts/export_schemas.py --check`; `python3 scripts/export_error_catalog.py --check` | Passed locally | 272-ID inventory (32 passed, 8 partial, 232 planned), 49-code registry, and generated artifact currency; does not assert full acceptance. |
| `mkdocs build --strict` | Passed locally | Generated documentation in `docs/`. |
| `python3 scripts/verify_release.py --output reports/release-preflight-2026-10-21.json` | 11-check local preflight; [preflight record](../reports/release-preflight-2026-10-21.json) | This preflight is narrower than Milestone 7: target-OS CI, packaged GUI, axe/keyboard, mutation, and graph performance gates remain. |
| `python3 scripts/benchmark_kernel.py` | 100-event replay max 0.0003 s, packet max 0.0015 s, development sidecar handshake max 0.0517 s; [benchmark record](../reports/benchmark-kernel.json) | Current macOS host, 5/5/3 samples; not the reference-machine or 300-node graph gate. |

No complete GUI end-to-end run, accessibility audit, multi-platform package test, performance budget measurement, mutation test, real human study, or independent scorecard review has been recorded. The internal [codebase review](SRS-033-Codebase-Review-2026-10-21.md) is not independent sign-off. Do not mark the matching acceptance gates complete from the checks above.

## Work remaining for the SRS release

The most consequential software gaps are independent invariant/golden-history evidence; robust semantic grounding; model adapters, cassettes, and budgets; and GUI interaction/accessibility/performance gates. Milestones 6 and 7 remain open. The human study, interpretation of realized ablations, independent review, and release sign-off belong to Milestone 9. Revised Milestones 5 and 8 pass their local software gates; this does not imply full SRS acceptance.
