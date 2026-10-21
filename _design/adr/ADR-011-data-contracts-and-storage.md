# ADR-011: JSON contracts and the NDJSON source of truth

**Status:** Accepted for the bounded release, 2026-10-20  
**Applies to:** Milestones 0–1; REQ-009–019, REQ-119–120, REQ-147–152

## Decision

Keep JSON fixture/contract documents and hashed NDJSON event streams as the required project format. Define typed Python contracts and export machine-readable schemas for the sidecar and frontend. Runtime validators remain authoritative; TypeScript types are derived from or checked against those contracts. SQLite is optional and is not on the release critical path. A snapshot is a verified cache, never canon.

For a format change, read the old bytes, verify their original hash, up-cast in memory, and leave sealed files unchanged. New writes use the current schema. Event schema 2 adds explicit `source_kind: authored`; schema-1 story and discourse events receive that field only in the reducer view. Evaluation claims retain their original payload. The version-1 line and ID remain unchanged when a version-2 event is appended. Project metadata stays format version 1. A further migration needs a golden fixture and a round-trip test before increasing `schema_version`.

## Reason

The existing app already writes local JSON/NDJSON projects. Replacing that format merely to match the proposed module layout would risk users' sealed history. Canonical JSON also supports deterministic hashes and portable inspection. This is a deliberate deviation from the Implementation Plan's Pydantic/YAML-first layout; Python runtime validation and published JSON schemas are the compatibility boundary.

## Consequences

- Fixtures and contracts can be imported as JSON now; unsafe YAML tags are rejected. A safe YAML importer can be added behind the same validators if needed.
- Event streams are never modified by schema up-casts. Historical bytes and IDs stay verifiable.
- Schema drift is a CI failure once contract export and TypeScript checks are in place.
- The researcher should decide whether human-authored YAML is needed before adding that format.
