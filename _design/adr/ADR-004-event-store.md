# ADR-004: NDJSON is the default event store

**Status:** Accepted, 2026-10-20

The project folder uses hashed NDJSON streams as canon. SQLite remains optional. A command replaces one stream atomically after complete validation; immutable sealed lines are preserved. Snapshots are verified caches. See [ADR-011](ADR-011-data-contracts-and-storage.md) and [ADR-012](ADR-012-process-and-transactions.md).
