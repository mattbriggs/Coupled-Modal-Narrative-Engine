# Read the result

## Concept — four different outputs

| Output | What it answers | Where to find it |
|---|---|---|
| Passage | What does the reader see? | Passage view; `prose` in run JSON; exported report |
| Findings and stages | Did the current checks pass? | Pipeline view; `findings`, `stages`, and `status` in run JSON |
| Projection | What does the engine derive at this point? | Mind, Provenance, Motif, strain views; scrubber; `scrub.projection` |
| Trace | What supports this selected story event? | Trace details; `trace.query` |

## Procedure — read the sample output

1. Select C0 and read the passage in discourse order. Notice how the chair and bowl recur while the ending leaves the central question open.
2. Select C1, C2, then C3. Compare the interpretation of earlier events, not only the final action. C1 changes a belief, C2 adds a possible scenario, and C3 changes the categories Mara uses.
3. In **Story**, inspect the causal chain and strain values. In **Discourse**, inspect which story event each act references, what it reveals, and what it withholds.
4. Scrub to an earlier story sequence and compare the actor and reader projections with the final state. Discourse can point back to an earlier event; telling order is independent of story order.
5. Open **Trace** on a story event. Read its causal parents, observers, disclosures, and later interpretations. A later interpretation may target an earlier sequence without rewriting that event.
6. Check **Pipeline** and the findings list. `passed` means the implemented checks found no violation; it is not a literary quality score.

## Structure — run JSON

```json
{
  "run_id": "run_…",
  "branch_id": "branch_…",
  "conditions": ["C3"],
  "packet_hash": "…",
  "prose": "The passage…",
  "findings": [],
  "stages": [{"condition": "C3", "stage": "Check", "status": "passed"}],
  "projection_hashes": {"actor_a": "…", "reader": "…"},
  "status": "passed",
  "realizer": "deterministic-template-v2"
}
```

The actual run also contains `run_sequence` and all seven stage entries. Hashes identify packet and projection content; they are useful for comparing repeatable runs, not for interpreting the prose.

## Principle — a finding is a diagnostic

`E-PROSE-WORDS` means the generated word count is outside the contract's bounds. `E-PROSE-FORBIDDEN` means a forbidden string appears in the prose. `E-RUN-CONTRACT` means a required story condition is absent from the grounded story facts. `E-RUN-EMPTY` and `E-RUN-PLAN` mean story or discourse is missing. A failed stage indicates the layer where the current implementation classifies the problem. [Troubleshooting](troubleshooting.md) gives recovery steps.

## Fact — what the strain chart shows

`strain_bp` is an author supplied value from 0 to 10,000 at each story event. The chart plots that sequence; it is not a measurement of reader emotion. The current telling tension projection is a simple function of the number of withheld claims. Use these numbers to inspect your own design choices, not as an external evaluation.
