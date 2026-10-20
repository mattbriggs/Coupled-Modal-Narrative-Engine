# Current limits and roadmap

This page distinguishes the running app from the broader SRS-033 design. The detailed requirement and scenario checkpoint lives in [_design/SRS-033-Implementation-Status.md](https://github.com/mattbriggs/Coupled-Modal-Narrative-Engine/blob/main/_design/SRS-033-Implementation-Status.md).

| Area | Implemented now | Planned in the source design |
|---|---|---|
| Authoring | Story/discourse drafts, preview, seal, fork, basic compare | Full fixture/mind/rule palette editing and richer diff tools |
| State | Deterministic replay, six projections, basic revisions and formula preconditions | Formal modal/conceptual revision operators and richer provenance |
| Realization | Offline authored text/template, packet and run hashes | Model adapters, budget and cassette record/replay |
| Checking | Structural invariants, word bounds, literal forbidden strings | Semantic grounding and private-knowledge leak detection |
| Evaluation | Individual Markdown run export | Blinded sets, evaluator workflow, import, statistical analysis |
| Recovery | Persistent drafts, project lock, sidecar restart once | Complete crash recovery and published-run replication |

Scenario S-04's diagnostic flow is useful today, but a subtle claim can pass the basic checker. Scenarios S-07–S-12 specify research/evaluation or model service features that are not in this implementation. The user manual confines procedures to available actions and marks the limits at each relevant step.
