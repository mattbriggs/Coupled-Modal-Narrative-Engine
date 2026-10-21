# ADR-013: Release and research defaults

**Status:** Accepted defaults; individual decisions reopen at their named gate, 2026-10-20  
**Applies to:** Milestones 0, 4–8

| Question | Current decision | Revisit before |
|---|---|---|
| Desktop stack | Tauri 2, Rust bridge, React/TypeScript frontend, Python domain sidecar | Any framework replacement |
| Release target | Unsigned macOS developer bundle first; Python/frontend/docs CI on macOS, Linux, Windows | Milestone 7 installer/signing gate |
| Run execution | Keep deterministic offline template mode; move long runs to cancellable workers for Milestone 6 | Milestone 6 API freeze |
| Model vendor | None selected; build a fake adapter and cassette contract first | Milestone 4 vendor implementation |
| Credentials and privacy | Environment variables by default, no secrets in logs, explicit per-run opt-in before remote transfer | Milestone 4 adapter release |
| Voice exemplars | Ship no third-party exemplars; researcher supplies a rights-cleared profile | Milestone 3 voice-profile freeze |
| Evaluator workflow | File-based blinded set and structured response import; no evaluator app login | Milestone 5 protocol freeze |
| Study design | Research lead records sample-size rationale, recruitment/consent method, strain weights, and agreement metric before data collection | Milestones 2 and 5 |

These defaults resolve implementation branching without asserting a model choice, signing requirement, or human-study result. The research lead owns the study-specific decisions; the engineering lead owns the release-platform and schema decisions. A changed decision needs a new ADR and updated acceptance evidence.
