# Current limits and roadmap

This page distinguishes the running app from the broader SRS-033 design. The detailed requirement and scenario checkpoint lives in [_design/SRS-033-Implementation-Status.md](https://github.com/mattbriggs/Coupled-Modal-Narrative-Engine/blob/main/_design/SRS-033-Implementation-Status.md).

| Area | Implemented now | Planned in the source design |
|---|---|---|
| Authoring | Story/discourse drafts, preview, seal, fork, basic compare, fixture/contract JSON editing | Full concept/rule palette editing and richer diff tools |
| State | Deterministic replay, six projections, weighted strain/crisis gates, belief/modal/conceptual transitions, provenance traces, motif ledger, nine independent sealed-history fixtures, and seeded property checks | Broader formal semantics and full invariant evidence |
| Realization | Offline authored text/template, packet and run hashes, JSON adapter bridge, call/token/cost budget, and canonical cassette replay | Selected external vendor and release credential configuration |
| Checking | Structural invariants and sentence-level checks for selected access, disclosure, resolution, and voice rules | Stronger semantic grounding and adversarial corpus coverage |
| Evaluation | Individual Markdown export; fixed plans, 12 matched offline variants, blinded set, response import, descriptive report, seven realized controlled ablations, and a hashed generalization review packet | Human study, literary interpretation, and signed generalization decision (Milestone 9) |
| Recovery | Persistent drafts, project lock, sidecar retry for stateless validation calls only | Complete crash recovery and published-run replication |

The current checkpoint includes decision records, a 272-ID acceptance inventory, generated JSON Schema/TypeScript contracts, atomic batches, verified snapshots, local hash vectors, weighted crisis logic, study tooling, and adapter cassettes. The local Python suite has 103 tests. Milestones 0–4 remain open where cross-platform, semantic, vendor, or complete acceptance evidence is missing. Revised Milestones 5 and 8 pass their local software gates; Milestones 6 and 7 still need GUI and release evidence. Milestone 9 holds the human study and sign-off. The [detailed project roadmap](https://github.com/mattbriggs/Coupled-Modal-Narrative-Engine/blob/main/_design/SRS-033-Project-Roadmap.md) records the exact gates.

The [ten-category software review](code-review.md) ranks current code quality separately from the historical written-design score. It records the recent fixes to project switching, contract replacement, post-commit errors, study/RPC validation, background status snapshots, and sidecar retry policy.

Scenario S-04's diagnostic flow is useful today, but a subtle claim can still pass the deterministic checker. S-07–S-09 can be dry-run with synthetic responses; human results are not yet collected. S-10–S-12 now have an adapter/cassette API path; a release vendor and published-run replication test remain open. The user manual confines procedures to available actions and marks the limits at each relevant step.
