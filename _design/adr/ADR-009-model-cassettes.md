# ADR-009: Record and replay model calls

**Status:** Implemented adapter boundary; vendor release decision open, 2026-10-21

Every model adapter call passes through a canonical request/response cassette, per-run call/token/optional-cost budget, and offline replay. Record mode requires explicit data-transfer opt-in; the model process receives plain JSON through a researcher-supplied executable and obtains any credentials from its environment or ignored local configuration. Adapter exception text and standard error are not persisted. A missing or corrupt cassette raises `E-CASSETTE-001`, and a changed response for the same request is refused. Prose adapter failure falls back to the deterministic template without changing canon. A generated story proposal stays in diagnostic storage until the ordinary command validator accepts it.

No external vendor or release cost ceiling is selected. The offline fake and subprocess bridge exercise the contract, including a socket-blocked byte-identical replay and a five-call budget stopping the sixth call. A selected vendor and target-platform packaged tests remain Milestone 4 gate work.
