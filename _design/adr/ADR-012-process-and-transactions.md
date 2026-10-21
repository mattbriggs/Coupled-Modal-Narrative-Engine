# ADR-012: Single writer, readers, and atomic command batches

**Status:** Accepted for the bounded release, 2026-10-20  
**Applies to:** Milestones 0–1 and 6; REQ-011–013, REQ-127–128, REQ-152, REQ-166

## Decision

Allow one writer per project and read-only project instances while a writer holds the lock. The lock records PID, host, and start time. A stale lock is reported; clearing it is an explicit action after confirming the writer stopped. Sidecar writes are serialized. A command validates every proposed event against the evolving in-memory state and replaces its stream once, after all validation succeeds.

The current command surface emits one stream per command (`story` or `discourse`). A future cross-stream command requires a journal or other recoverable transaction protocol before it is exposed. Read-only calls may read committed files while a writer is active; no reader sees the writer's in-memory proposals.

Fixture and contract replacement revalidate sealed events and preconditions before writing. A failed project switch keeps the prior project and lock open. `command.submit` reports `accepted: false` only for a pre-commit validation error; an error after replacement has an uncertain outcome and must be checked against the stream before retrying.

## Reason

Validation and storage must share a clear commit point. An invalid second event must leave the first event unsealed. Lock state cannot be inferred from a path alone, especially across processes and hosts.

## Consequences

- A read-only open cannot save drafts, run, export, or append events.
- A power loss during replacement leaves the previous or complete new stream; a crash test is required at the release gate.
- Lock ownership must be checked before every mutating service call, including fixture/contract writes.
