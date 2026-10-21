# ADR-008: Closed formula AST

**Status:** Accepted, 2026-10-20

Preconditions use the bounded declarative AST in `src/cmne/formula.py`. Unknown operators, excess depth, and excess nodes are rejected; evaluation has no dynamic code execution. Richer entailment requires a versioned language decision and migration tests.
