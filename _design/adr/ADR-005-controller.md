# ADR-005: Controller stays outside the six machines

**Status:** Accepted, 2026-10-20

The controller orders validation, replay, packet building, and runs. It is not a narrative projection. The six projections retain distinct state and hashes, so control flow cannot be mistaken for an additional character or reader machine.
