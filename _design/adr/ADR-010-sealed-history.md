# ADR-010: Sealed events are immutable; edit by fork

**Status:** Accepted, 2026-10-20

There is no update or delete operation for a sealed event. A correction forks at an existing sequence and seals a new suffix. Import and schema up-casts must preserve historical bytes and event IDs. The store verifies the shared prefix on read.
