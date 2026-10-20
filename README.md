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
python -m pip install -e '.[bundle]'
cd app
npm ci
cd ..
```

The Python package and PyInstaller are installed in `.venv`; `npm ci` installs the exact frontend dependencies from `app/package-lock.json`. Activate the environment again with `source .venv/bin/activate` in each new terminal when running Python or the development app.

## Build and launch the macOS app

After installing dependencies as above:

```sh
./build_app.sh --skip-install
./launch_app.sh
```

`build_app.sh` builds the React frontend, packages the Python sidecar with PyInstaller, compiles the Tauri shell, and produces the unsigned local bundle at `app/src-tauri/target/release/bundle/macos/CMNE Workbench.app`. `launch_app.sh` opens that built app. When invoked by path, either script works from any directory.

For a fresh checkout, `./build_app.sh` also creates `.venv` if needed and installs both Python and Node dependencies before building. Use `./build_app.sh --skip-install` for later rebuilds when dependencies are already installed. The build script prefers rustup's toolchain when both rustup and an older system Cargo are present.

The Tauri build runs `scripts/prepare_sidecar.py` to create the target-named Python executable included as `externalBin`. Developer builds use the virtual environment's Python; the packaged app includes Python and does not need `.venv` to launch. The Tauri shell restarts the sidecar once after a broken pipe.

To run the development app without packaging, activate the virtual environment and run:

```sh
source .venv/bin/activate
cd app
npm run tauri -- dev
```

The first launch opens the bundled Mara and Len sample in `~/Documents/CMNE/Mara and Len`. It includes separate C0–C3 branches that share S01–S07 and diverge through fact, belief, modal, and conceptual changes. **Run C0–C3** runs all four with the offline realizer. To create another project, use the project menu. To edit canon, select a story event and choose **Fork from here**. The new branch contains editable copies of that event and its suffix. To add an event or discourse act, open the appropriate lens, choose **Add**, fill in the inspector, connect references, then **Seal draft**.

The workbench provides a seven-lens graph, a keyboard-accessible outline, a story and discourse scrubber, a strain chart, trace details, branch comparison, deterministic realization, and Markdown report export. It saves projects locally and makes no model API calls.

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
(cd app && npm run build)
(cd app/src-tauri && cargo check)
```

The tests cover deterministic replay, invariant rejection without history mutation, fork isolation, draft seal, project locking, protocol handshake, and a run's separation from canon.

## Project files

```text
project.cmne.json
.cmne.lock
fixtures/active.json
contracts/active.json
branches/<branch>/story.ndjson
branches/<branch>/discourse.ndjson
branches/<branch>/evaluation.ndjson
drafts/<draft-id>.json
packets/<packet-hash>.json
runs/<run-id>.json
exports/<run-id>.md
```

Sealed event files are treated as immutable history. A branch copies a verified prefix and keeps its own later events. Writes replace a complete stream file atomically. Replays derive six projection hashes from integer-valued state and canonical JSON. The project lock allows one writer; opening the same project in a second process returns `E-LOCK-001`.

## Implementation status

| Area | Current state |
|---|---|
| Desktop shell and sidecar | Tauri command relay, protocol handshake, allow-listed RPC, bundled Python executable |
| Workbench | Seven graph lenses, draft editing and sealing, branch fork and compare, outline, inspector, scrubber, chart, passage view, report export |
| Python kernel | Contract and fixture checks, bounded formula AST and preconditions, integrity-hashed NDJSON streams, deterministic replay and six named projections, basic belief, modal, and conceptual transitions, observer access check, discourse grounding, project lock |
| Realization | Offline template realizer, packet hash, word-bound and forbidden-assertion checks |
| Research pipeline | **Still partial:** formal modal and conceptual revision operators, provenance graph, model adapters, record/replay cassettes, blinded evaluation, full grounding checker, and the remaining SRS acceptance gates |

The current `run.start` executes one selected branch or all four seeded conditions with distinct deterministic passages. The desktop build is a useful local authoring instrument; it is not yet the complete research instrument specified by SRS-033.
