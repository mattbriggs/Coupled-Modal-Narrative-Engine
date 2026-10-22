# Software code review

The 2026-10-21 review examined the Python kernel and sidecar, the Tauri bridge, the React workbench, tests, build checks, and documentation. The [full review in `_design`](https://github.com/mattbriggs/Coupled-Modal-Narrative-Engine/blob/main/_design/SRS-033-Codebase-Review-2026-10-21.md) records the evidence and remaining gates. These are **software** scores; the older 100/100 package score assesses the written design.

| Category, ranked by current evidence | Score / 10 | Gate still open |
|---|---:|---|
| Type and API contracts | 9 | Cross-language contract depth |
| Determinism and sealed history | 8 | Full invariant and cross-OS vectors |
| Error handling and recovery | 8 | Packaged GUI crash journey |
| Sidecar and process boundary | 8 | Real restart and fault matrix |
| Documentation and traceability | 8 | Full AC/GAC evidence |
| Test behavior and independence | 8 | Nine separate histories pass; complete epiphany semantics, mutation, and GUI tests remain |
| Code organization and maintainability | 7 | Large UI/project modules |
| Build and portability | 7 | Clean-checkout three-OS CI and packages |
| Python coverage and regression depth | 7 | Branch/mutation and lower-coverage boundaries |
| Workbench usability and accessibility | 5 | Keyboard, assistive-tech, graph performance, GUI E2E |

A 10 means the relevant SRS release gate has passed on supported targets. None has that evidence yet. The review did fix failed project switching, contract changes that could invalidate sealed crises, post-commit command reporting, malformed study and RPC inputs, mutable background status snapshots, automatic replay of uncertain writes, and a stale draft pointer. Nine separate golden histories now check machine outcomes independently of the bundled sample. Seeded properties and model cassette tests extend that evidence. Python passes 103 behavior tests, 89.9% executable-line coverage (3,153/3,509), Mypy, and Ruff; Rust Clippy and its recovery-policy unit test pass. These checks are part of the configured CI, which has not yet run from a clean checkout on all targets.

The [roadmap](roadmap.md) lists the software gates before Milestone 9. Milestone 9 requires human evaluation, independent review, and release sign-off.
