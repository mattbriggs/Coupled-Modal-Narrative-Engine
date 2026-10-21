# Codebase review — 2026-10-21

This review scores the **running software**, not the historical 100/100 design-package score in [SRS-033-R](SRS-033-Package-Review-Scorecard.md). A 10 means the full relevant SRS software gate is demonstrated on release targets. Scores are judgments based on the evidence below; they are not a percent complete. Human literary evaluation and release approval remain Milestone 9.

## Verified changes

- Project switching now keeps the previous project and its writer lock when a new open or create fails. Reopening the same project is stable; changing access mode requires an explicit close.
- Contract replacement now revalidates every sealed story event and its preconditions against the proposed contract before writing. A threshold that invalidates a sealed crisis is rejected without changing the saved contract.
- `command.submit` catches validation errors only before the atomic append. A projection error after commit can no longer return `accepted: false` with an unchanged hash. Clients must inspect the saved stream after an ambiguous post-commit error.
- The JSON-RPC boundary rejects non-object requests and parameters. Study plans and response batches reject malformed nested measure names and passage IDs with field paths.
- Background `run.status` returns a locked deep snapshot; a worker cannot mutate a previously returned status object. The Tauri bridge retries only stateless calls after a child failure; it never resends a project mutation whose result may already be on disk.
- Removed unused imports and a placeholder UI recovery comment; stale draft pointers are deleted when switching branches. Python source passes Mypy; Python code passes Ruff `F,B,UP,SIM`; Rust passes Clippy with warnings denied. These checks are in CI and local preflight.
- The graph canvas now exposes a region and announces connection mode with a status role; Fit respects reduced-motion preference. This is a code review improvement, not a completed assistive-technology audit.

The new tests assert persisted events, unchanged contract bytes, lock ownership, returned error shapes, and immutable progress snapshots. Existing failure-injection tests cover atomic stream replacement and process death. The old test named “nine golden histories” exercised nine predicates over one bundled sample; it is now accurately named as sample-history observations. A new `tests/golden_histories.json` supplies nine separate sealed histories with explicit expected projections, including observer/reader divergence, a mistaken belief, modal expansion, conceptual split, and crisis. Broader property and mutation evidence remains outstanding.

## Ten-category software scorecard

| Rank | Category | Score / 10 | Evidence and reason it is below 10 |
|---:|---|---:|---|
| 1 | Type and API contracts | **9** | Mypy passes for 15 source files; generated JSON Schema/TypeScript and error catalog checks pass. Dynamic JSON remains permissively typed and cross-language contract tests are incomplete. |
| 2 | Determinism and sealed history | **8** | Canonical hashes, atomic same-stream batches, lock checks, snapshots, up-casts, and failure injection pass locally. Full INV-01–INV-18 evidence and cross-OS vectors are open. |
| 3 | Error handling and recovery | **8** | Project switch, contract edit, malformed input, post-commit response, sidecar retry, and draft pointer defects were corrected. Full packaged GUI crash recovery is untested. |
| 4 | Sidecar and process boundary | **8** | Handshake, allowlist, malformed-input errors, background runs, locked status snapshots, and bundled-sidecar smoke pass. A real Rust/GUI restart journey and process fault matrix remain open. |
| 5 | Documentation and traceability | **8** | Status, roadmap, design/API/user pages, 272-ID inventory, generated contracts, and strict MkDocs build describe current behavior. Most original AC/GAC IDs lack complete passing evidence. |
| 6 | Test behavior and independence | **8** | 88 Python tests and one Rust recovery-policy test exercise state changes and failures; nine independent sealed-history fixtures check projections. Mutation threshold, frontend interaction tests, and GUI E2E are missing. |
| 7 | Code organization and maintainability | **7** | Domain modules have clear boundaries and pass typing/lint. `project.py` and `App.tsx` are large, the UI has few isolated components, and no frontend unit suite exists. |
| 8 | Build and portability | **7** | Frontend build, Rust Clippy/test, strict MkDocs, local macOS bundle and packaged-sidecar smoke pass. New CI has not run from a clean checkout on three OS targets; Windows/Linux packages and signing are unverified. |
| 9 | Python coverage and regression depth | **7** | 88 passing Python tests cover 2,785 of 3,116 executable lines (89.4%). The report is line-only; CLI 69.9% and sidecar 60.5% lag, and branch/mutation evidence is absent. |
| 10 | Workbench usability and accessibility | **5** | Seven lenses, draft workflows, outline, study panel, and keyboard shortcuts exist. Full canvas/outline parity, assistive-tech verification, 300-node performance, and packaged GUI journeys have not passed. |

No category is scored 10 because the required release evidence is incomplete. The ranking is by current score, then the consequence of the remaining gate. The 10/10 target for each category is its named gate in the [roadmap](SRS-033-Project-Roadmap.md), especially Milestones 0–4, 6, and 7. Milestones 5 and 8 pass their revised **local software** gates; Milestone 9 alone owns human judgment and sign-off.

## Verification and limits

| Check | Result | Limit |
|---|---|---|
| Python tests | 88 passed | Selected behavior, not full AC/GAC acceptance |
| Python line coverage | 89.4% (2,785/3,116) | Standard-library executable-line tracer, not branch or mutation coverage |
| Mypy | 15 source files, no errors | `--ignore-missing-imports`; dynamic JSON is not fully statically proved |
| Ruff | `F,B,UP,SIM` passed | Line length/style are not a quality gate |
| Rust | Clippy with `-D warnings`; one unit test passed | No real packaged GUI restart test |
| React | TypeScript and Vite production build passed | No automated interaction/accessibility suite |
| Docs | Strict MkDocs build passed | Manual has not been independently tested with readers |

The acceptance inventory is still **32 passed, 8 partial, 232 planned** of 272 IDs under the original SRS wording. A local preflight, a design score, and line coverage do not close those gates. The remaining software work is recorded in the roadmap before Milestone 9.
