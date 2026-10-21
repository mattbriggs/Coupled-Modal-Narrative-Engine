# ADR-002: Python contracts and exported JSON Schema

**Status:** Accepted as a change to the implementation plan, 2026-10-20

The existing Python validators remain authoritative. `src/cmne/contracts.py` defines typed boundary objects and JSON Schema shapes; `scripts/export_schemas.py` generates the schema bundle and TypeScript types checked by CI. Runtime semantic checks remain in `core.py`. The proposed Pydantic dependency is deferred because replacing the existing validators now would create a second migration risk without improving sealed-project compatibility. A later Pydantic adoption must prove equivalent validation and preserve the generated boundary. See [ADR-011](ADR-011-data-contracts-and-storage.md).
