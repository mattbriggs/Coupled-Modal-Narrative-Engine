# ADR-001: Sidecar over standard input JSON-RPC

**Status:** Accepted, 2026-10-20

The Tauri shell relays an allowlisted, line-framed JSON-RPC 2.0 protocol to the Python sidecar. Python owns validation and narrative state. The shell supervises the child and checks the protocol major version at handshake. This avoids a local network listener and preserves one kernel for the CLI and desktop app. See [ADR-012](ADR-012-process-and-transactions.md) for write serialization.

**2026-10-21 recovery rule:** A broken pipe or unexpected child exit can occur after a write commits but before its response arrives. The shell retries only stateless `app.hello`, `fixture.validate`, and `contract.validate` calls. It returns an uncertain-outcome error for project calls and requires the author to reopen and inspect saved state before retrying. Stateful reads are not automatically retried because a fresh child has no open project.
