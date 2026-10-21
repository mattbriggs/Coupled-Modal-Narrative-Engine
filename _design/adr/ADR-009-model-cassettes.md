# ADR-009: Record and replay model calls

**Status:** Accepted target for Milestone 4, 2026-10-20

Every future model adapter call must have a recorded request/response cassette, budget accounting, and offline replay. No vendor is selected yet. The deterministic template path remains the baseline. The cassette implementation and network-blocked replay gate are pending; this ADR records the required boundary, not delivered behavior.
