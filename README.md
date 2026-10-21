# Coupled Modal Narrative Engine

[![GitHub stars](https://img.shields.io/github/stars/mattbriggs/Coupled-Modal-Narrative-Engine?style=flat-square)](https://github.com/mattbriggs/Coupled-Modal-Narrative-Engine/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/mattbriggs/Coupled-Modal-Narrative-Engine?style=flat-square)](https://github.com/mattbriggs/Coupled-Modal-Narrative-Engine/issues)
[![GitHub last commit](https://img.shields.io/github/last-commit/mattbriggs/Coupled-Modal-Narrative-Engine?style=flat-square)](https://github.com/mattbriggs/Coupled-Modal-Narrative-Engine/commits)

A local desktop workbench for authoring a bounded scene as sealed story events and discourse acts. A Python sidecar owns validation, replay, branching, scene packets, and deterministic prose. Tauri 2 hosts the React interface and relays JSON-RPC over the sidecar's standard input and output.

The source specifications are in [`_design/`](./_design/). This repository currently implements the working foundation and the Mara/Len sample. The [implementation status](#implementation-status) below identifies the larger research features still to build.

## Install dependencies (macOS)

Prerequisites: Python 3.11+, Node 22+ with npm, Rust 1.90+ with Cargo, and the macOS Tauri prerequisites. Run these commands from the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[bundle,docs,dev]'
cd app
npm ci
cd ..
```

The Python package, PyInstaller, MkDocs, Ruff, and Mypy are installed in `.venv`; `npm ci` installs the exact frontend dependencies from `app/package-lock.json`. Activate the environment again with `source .venv/bin/activate` in each new terminal when running Python or the development app.

## Build and launch the macOS app

After installing dependencies as above:

```sh
./build_app.sh --skip-install
./launch_app.sh
```

`build_app.sh` builds the React frontend, packages the Python sidecar with PyInstaller, compiles the Tauri shell, and produces the unsigned local bundle at `app/src-tauri/target/release/bundle/macos/CMNE Workbench.app`. `launch_app.sh` opens that built app. When invoked by path, either script works from any directory.

For a fresh checkout, `./build_app.sh` also creates `.venv` if needed and installs both Python and Node dependencies before building. Use `./build_app.sh --skip-install` for later rebuilds when dependencies are already installed. The build script prefers rustup's toolchain when both rustup and an older system Cargo are present.

The Tauri build runs `scripts/prepare_sidecar.py` to create the target-named Python executable included as `externalBin`. Developer builds use the virtual environment's Python; the packaged app includes Python and does not need `.venv` to launch. After a sidecar failure, the shell retries only stateless validation calls. Reopen and inspect the project before repeating an interrupted project operation.

To run the development app without packaging, activate the virtual environment and run:

```sh
source .venv/bin/activate
cd app
npm run tauri -- dev
```

The first launch opens the bundled Mara and Len sample in `~/Documents/CMNE/Mara and Len`. It includes separate C0–C3 branches that share S01–S07 and diverge through fact, belief, modal, and conceptual changes. **Run C0–C3** runs all four with the offline realizer. To create another project, use the project menu. To edit canon, select a story event and choose **Fork from here**. The new branch contains editable copies of that event and its suffix. To add an event or discourse act, open the appropriate lens, choose **Add**, fill in the inspector, connect references, then **Seal draft**.

The seeded C0–C3 sample now assembles a distinct 700–1,100-word passage for each condition from authored offline prose. It does not call a language model. After rebuilding, run the scene again to replace a previously saved short passage; existing sealed events and discourse remain intact. An edited discourse cue is used as written. Other projects realize their own discourse text, so their passage length depends on what the author supplies.

The workbench provides a seven-lens graph, a keyboard-accessible outline, a story and discourse scrubber, a strain chart, trace details, branch comparison, deterministic realization, and Markdown report export. It saves projects locally and makes no model API calls.

The **Evaluation study** section can freeze an analysis plan, generate three matched offline composition variants per C0–C3 condition, export a randomized public set with a separate private key, import cited-span responses, realize seven controlled ablations, and save a descriptive report and generalization review packet. Background scene runs show progress and can be cancelled between conditions. The Fixture lens includes validated fixture and contract JSON editors. See the [evaluation manual](./site/manual/evaluate-study.md) before sharing passages with readers.

Keyboard shortcuts: `Alt+1` through `Alt+7` switch lenses, `Alt+O` toggles the outline, `Ctrl/Cmd+K` adds a node, `C` starts a connection from the selected node, `Ctrl/Cmd+Z` and `Ctrl/Cmd+Shift+Z` undo and redo draft edits, and `Ctrl/Cmd+Enter` seals a draft.

## Run the Python kernel directly

After installing the Python package in the virtual environment, create and run a sample project:

```sh
source .venv/bin/activate
cmne create /tmp/cmne-sample --sample
cmne run /tmp/cmne-sample
```

The transport can be tested without Tauri:

```sh
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"app.hello","params":{"protocol_version":"1.0"}}' | cmne-sidecar
```

The sidecar sends one JSON-RPC object per line to standard output. Logs and errors go to standard error. `app.hello` must precede other methods.

## Verify

```sh
source .venv/bin/activate
python -m unittest discover -s tests -v
mypy src --ignore-missing-imports --no-incremental
ruff check src scripts tests --select F,B,UP,SIM
python scripts/coverage_report.py
python scripts/benchmark_kernel.py
python scripts/verify_release.py
(cd app && npm run build)
(cd app/src-tauri && cargo clippy --locked --all-targets -- -D warnings)
```

The standard-library coverage script reports executable-line coverage per Python module. It does not measure branch coverage, the frontend, or Rust. The tests cover replay, invariants, provenance, revision, prose checks, blinded exports, atomic response import, report calculations, and background cancellation.

`verify_release.py` saves a local preflight report under `reports/`. Its passing result covers Python tests, typing, lint, frontend, Rust (on macOS), generated artifacts, and documentation. The full release gate also needs target-OS CI, packaged GUI, accessibility, performance, mutation, and AC/GAC evidence.

To check the milestone acceptance inventory, generated contracts, and error catalog:

```sh
python scripts/check_acceptance.py
python scripts/export_schemas.py --check
python scripts/check_error_catalog.py
python scripts/export_error_catalog.py --check
```

The inventory lists every SRS requirement and acceptance criterion with conservative status. Its `--strict` mode is a release gate and is expected to fail until all mapped criteria pass. The new GitHub Actions workflow runs Python, frontend, and docs checks on macOS, Linux, and Windows, plus a Rust check and packaged sidecar smoke on macOS.

## Documentation

The [MkDocs source](./site/index.md) contains the task-based user manual, implementation design, and API reference. Install the documentation dependencies in the same virtual environment:

```sh
source .venv/bin/activate
python -m pip install -e '.[docs]'
mkdocs serve
```

Open the local address printed by MkDocs to read the Material site. To create static HTML instead, run `mkdocs build --strict`. Markdown source is in `site/`; the generated HTML target is `docs/` for GitHub Pages. The diagrams use Mermaid fences in the Markdown source.

## Project files

```text
project.cmne.json
.cmne.lock
fixtures/active.json
contracts/active.json
branches/<branch>/story.ndjson
branches/<branch>/discourse.ndjson
branches/<branch>/evaluation.ndjson
snapshots/<branch>.json
drafts/<draft-id>.json
packets/<packet-hash>.json
runs/<run-id>.json
exports/<run-id>.md
study/plans/<plan-hash>.json
study/keys/<study-id>.json
study/responses/<study-id>.json
study/reports/<study-id>.json
study/ablations/<branch>/<name>.json
study/decision-packets/<study-id>.json
exports/evaluation/<study-id>/public/
```

Sealed event files are treated as immutable history. A branch copies a verified prefix and keeps its own later events. A command validates all of its same-stream events before one atomic stream replacement. Replays derive six projection hashes from integer-valued state and canonical JSON; snapshots are verified caches. The project lock allows one writer and concurrent read-only opens; a second writer receives `E-LOCK-001`. Clearing a stale lock is an explicit action.

## Implementation status

| Area | Current state |
|---|---|
| Desktop shell and sidecar | Tauri command relay, protocol handshake, allow-listed RPC, bundled Python executable |
| Workbench | Seven graph lenses, fixture/contract JSON editing, draft editing and sealing, branch comparison, outline, scrubber, chart, passage view, background run progress/cancel, individual report export, and study controls |
| Python kernel | Typed contracts, bounded formula AST, integrity-hashed NDJSON, atomic batches, verified replay, six projections, weighted strain/crisis gates, revision operators, provenance traces, and motif ledger |
| Realization | Filtered deterministic packet, offline template realizer, sentence findings for selected grounding, disclosure, and voice rules |
| Research pipeline | Frozen analysis plans and amendments, matched offline variants, blinded export, atomic response import, descriptive report, seven saved controlled ablation passages, and a hashed generalization review packet. Human evaluation and sign-off are Milestone 9. |

The revised Milestones 5 and 8 pass their local software gates. Milestones 6 and 7 still need full GUI and release verification; Milestone 9 holds the human study and sign-off. Earlier milestones retain their own open gates. See the [current roadmap](./_design/SRS-033-Project-Roadmap.md) for exact status.

The [dated codebase review](./_design/SRS-033-Codebase-Review-2026-10-21.md) ranks ten software quality categories, records the behavior and recovery fixes, and lists the evidence needed for each category to reach 10/10. The 100/100 score in the historical package review applies to the written design, not this implementation.
