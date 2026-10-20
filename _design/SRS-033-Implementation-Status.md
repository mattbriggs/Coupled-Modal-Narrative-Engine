# SRS-033 implementation status

| Field | Value |
|---|---|
| Date | 2026-10-19 |
| Scope | Current repository implementation, compared with the SRS-033 v0.2 design baseline |
| Status | Working local foundation; full research release is incomplete |

This is the implementation record for the design package. The SRS requirements, acceptance criteria, scenarios, diagrams, and proposed module layouts remain **targets** unless a row below explicitly describes delivered code. “Implemented” here describes the available behavior; it does not mean that every linked SRS acceptance criterion has passed. The package review's 100/100 is a score for the *written specification*, not the application.

## What runs now

| Area | Delivered behavior and source | Limit |
|---|---|---|
| Desktop | Tauri 2 Rust shell in `app/src-tauri/`; React 19, TypeScript, and Vite in `app/src/`; Rust relays an allowlisted JSON-RPC 2.0 method set to a Python process over line-framed standard input/output. `app.hello` checks protocol major version; a broken pipe triggers one restart. | No asynchronous run notifications or cancellation. The Rust shell is a transport, not a domain implementation. |
| Distribution | `scripts/prepare_sidecar.py` makes a development wrapper or PyInstaller executable for Tauri `externalBin`; an unsigned macOS `.app` bundle has been built. | Windows/Linux packages, signing, installation, and a packaged GUI smoke test have not been verified. |
| Project and kernel | `src/cmne/core.py`, `formula.py`, and `project.py` validate basic fixture, contract, story, and discourse data; evaluate a bounded closed formula AST; write hashed NDJSON streams; replay into six named projections; and save local JSON packets and runs. Event IDs and projection hashes use canonical JSON and SHA-256. | The six projections and belief/modal/conceptual transitions are narrow implementations of the design. There is no full formal semantics, schema up-casting, Pydantic contract layer, provenance graph, or cross-platform hash-vector gate. |
| Authoring | Seven lenses (Fixture, Story, Discourse, Mind, Provenance, Motif, Pipeline), SVG graph, inspector, outline/table view, connection validation, story/discourse drafts, preview/seal, fork from sealed events, basic branch comparison, scrubber, strain chart, and trace details. Drafts persist on disk and can be recovered; undo/redo is in memory (50 steps). | Fixture/Mind/Motif are chiefly views, not complete graph editors. No palette drag/drop, saved manual layout, minimap, semantic zoom, full overlay set, visual graph diff, or complete keyboard/table parity. |
| Sample and runs | `src/cmne/sample.py` seeds Mara and Len with story events S01–S10, discourse acts D01–D07, and C0–C3 branches sharing S01–S07. A synchronous `run.start` can run one branch or all four. Each condition yields a distinct offline template passage. Seven stages per run are recorded; the Pipeline lens shows the completed result. Markdown report export is available. | No model API adapter, record/replay cassette, call budget, live progress, cancelable worker, blinded study, response import, or statistical analysis. The sample contract permits 0–1100 words, so it does not enforce the SRS's 700–1100-word experiment. |
| Checks | The realizer checker tests word bounds, selected forbidden assertions, and missing required story/discourse material. Basic discourse and observation validation occurs before seal. | It does not perform the SRS's full private-cognition, unresolved-question, figurative-language, voice, or span-level grounding checks. A passing run is not proof of literary or study validity. |

## Current architecture and files

```text
React UI (app/src/App.tsx, GraphCanvas.tsx)
    -> Tauri invoke rpc_call (app/src-tauri/src/lib.rs)
    -> Python JSON-RPC dispatcher (src/cmne_sidecar/server.py)
    -> local kernel/project service (src/cmne/*.py)
    -> JSON metadata, fixture, contract, drafts, packets, runs;
       hashed NDJSON story/discourse/evaluation streams
```

The current project format is `project.cmne.json`, `.cmne.lock`, `fixtures/active.json`, `contracts/active.json`, `branches/<id>/{story,discourse,evaluation}.ndjson`, `drafts/<id>.json`, `packets/<hash>.json`, `runs/<id>.json`, and `exports/<id>.md`. The lock contains a PID; a second writer is refused. Streams are rewritten atomically as whole files for append, and a fork copies and verifies a shared prefix. This differs from the proposed YAML/Pydantic layout, append transaction model, and richer lock record in IMPL-033.

The UI uses React state and custom SVG/HTML layout. React Flow, ELK, ECharts, Zustand, schema-generated forms, and the proposed testing/storybook stack in SRS-033-V and IMPL-033 are design options **not installed in this implementation**. The CLI is a small `argparse` entry point in `src/cmne/cli.py`, not the planned Typer command suite.

The sidecar currently exposes project creation/open/close/get, fixture and contract get/validate/save, branch list/fork/compare, event read and submit, graph get/connection validation, draft create/get/patch/preview/seal/delete, scrub projection, strain series, basic trace query, packet build/get, run start/status, and Markdown report export. `run.cancel` is a response stub because runs are synchronous. The RPC names are defined in `src/cmne_sidecar/server.py`; the Rust allowlist is in `app/src-tauri/src/lib.rs`.

## User workflow available today

1. Launch the app. On first use, it creates and opens the Mara/Len sample in `~/Documents/CMNE/Mara and Len`, or create/open a local project.
2. Inspect the seven lenses or outline, select story/discourse nodes, and scrub story or telling time. Add and seal story/discourse drafts. Fork a sealed story event to edit its suffix in a new branch.
3. Choose a seeded condition branch and run it, or run C0–C3 together. Inspect the saved pipeline status, passage, findings, strain chart, and trace details. Export the selected branch's latest run to Markdown.

The app performs the run synchronously. The pipeline display reflects the saved result after `run.start` returns. `run.cancel` reports that no asynchronous run is active. A basic `branch.compare` result names divergence and projection differences; it is not the designed diff overlay.

## Verification record

| Check | Result | Scope |
|---|---|---|
| `PYTHONPATH=src python3 -m unittest discover -s tests -v` | 18 tests passed | Replay/hash consistency, preconditions, rejection without history mutation, branch isolation, draft seal, writer lock, protocol handshake, sample C0–C3 run, and formula behavior. These are selected checks, not an AC-01–AC-42 or GAC-01–GAC-22 gate run. |
| `cd app && npm run build` | Passed | TypeScript check and Vite production build. |
| `cd app/src-tauri && cargo check` | Passed | Rust type/build check. |
| `cd app && npm run tauri -- build --bundles app` | Passed on macOS | Unsigned `.app` assembled with target-named bundled sidecar. |
| Bundled sidecar smoke | Passed | Sample creation, C0–C3 run, 28 passed stage records (7 per condition), and Markdown report export from the packaged Python executable. |

No complete GUI end-to-end run, accessibility audit, multi-platform package test, performance budget measurement, mutation test, or independent scorecard review has been recorded. Do not mark the matching acceptance gates complete from the checks above.

## Work remaining for the SRS release

The most consequential gaps are formal revision and crisis semantics; complete provenance and traceability; full grounding and voice checks; model adapters with cassettes and budgets; study preparation, blind export, response import, and analysis; and GUI interaction/accessibility/performance gates. IMPL-033 remains the roadmap for those targets. Prioritize the acceptance tests and update this record as each capability lands.
