# Data contracts and errors

All documents are JSON-compatible. IDs are strings. Basis-point values are integers in `0..10000`. Validators return a copy with defaults and, for fixture/contract, a `content_hash`.

The runtime shape definitions are in `src/cmne/contracts.py`. `scripts/export_schemas.py` generates `schema/cmne.schema.json` and `app/src/generated/contracts.ts`; CI checks that both match the Python definitions. Semantic checks such as access and disclosure grounding remain in the kernel validators. JSON imports reject duplicate keys and nonfinite values.

## Fixture and contract

```json
{
  "actors": [{"id":"mara","name":"Mara"},{"id":"len","name":"Len"}],
  "entities": [{"id":"chair","name":"Chair","kind":"object","motif":true}],
  "initial_facts": [],
  "style": {"focalizer":"mara","distance":"close"}
}
```

A fixture requires exactly two actors, each with unique `id` and `name`. Entities need unique IDs and names. Optional initial facts and style feed replay. A new project uses `actor_a` and `actor_b` placeholders and no entities.

```json
{
  "required_story_conditions": [],
  "forbidden_story_conditions": [],
  "facts_that_must_be_clear": [],
  "questions_that_must_remain_open": [],
  "prose_bounds": {"min_words":0,"max_words":1100},
  "strain_threshold_bp":6500,
  "strain_weights_bp":{"contradiction":2500,"unexplained":2000,"failed_prediction":2000,"repair_complexity":2000,"identity_goal":1500},
  "high_commitment_bp":7000,
  "repair_budget_bp":5000
}
```

Required and forbidden conditions may not overlap; a claim may not be both clear and open. Bounds must be ordered nonnegative integers. Strain weights must total 10,000 basis points. The run checks required story facts, selected grounding/voice rules, forbidden strings, and word bounds. Arbitrary open questions still require a reviewer or a project-specific rule.

## Story event payload

```json
{
  "title":"Mara finds the note",
  "kind":"observation",
  "description":"A note lies beneath the bowl.",
  "actor_ids":["mara"],
  "entity_ids":["bowl"],
  "causal_parents":["evt_…"],
  "observed_by":["mara"],
  "access_path":"perception",
  "world_facts":["note_under_bowl"],
  "strain_components_bp":{"contradiction":2000,"unexplained":7000,"failed_prediction":4000,"repair_complexity":3000,"identity_goal":4000},
  "preconditions":[]
}
```

`title` is required. `kind` defaults to `action` and may be `action`, `observation`, `utterance`, `recollection`, `decision`, `revision`, or `crisis`. Causal parents must be earlier sealed event IDs. Observation requires `observed_by` and an access path of `perception`, `testimony`, or `memory`. New assessments use five `strain_components_bp` values; replay retains historical `strain_bp` for older sealed events. A crisis also needs `crisis` with observer, accessible evidence sequence, commitment, and repair cost. Optional `interpretations` have observer, model version, claim, and earlier targets; revisions preserve earlier records. `belief_revision` has status, confidence, and accessible evidence. `modal_revision` can add/remove constraints or scenarios; `conceptual_revision` records new concepts and a migration map. Generated proposals use `source_kind: generated`, `proposal_id`, and `validator_id: cmne-command-validator-v2`.

## Discourse act payload

```json
{
  "title":"The note",
  "mode":"scene",
  "story_refs":["evt_…"],
  "text":"Under the bowl, a folded note waited.",
  "focalizer":"mara",
  "reveal":["note_under_bowl"],
  "cue":[],
  "withhold":[]
}
```

`title` is required. `mode` defaults to `scene` and also accepts `summary`, `ellipsis`, `pause`, `memory`, and `repetition`. Optional `narrative_time`, `duration_weight_bp`, `salience_bp`, and `variant` record telling choices. References must exist on the branch. Every revealed claim must occur in a referenced event's `world_facts`, unless `hypothetical` or `unreliable` is truthy. A claim already revealed cannot later be withheld. `text` becomes prose in the offline realizer.

## Formula AST

```json
{"op":"and","operands":[
  {"op":"atom","predicate":"note_under_bowl"},
  {"op":"believes","observer_id":"mara","operands":[
    {"op":"atom","predicate":"len_left"}
  ]}
]}
```

Operators: `atom`, `not`, `and`, `or`, `implies`, `necessarily`, `possibly`, `believes`, `suspends`, `in_scenario`. `atom` takes `predicate` as a string or `{name, arguments, polarity}` object. `not`, the two modal operators, `believes`, `suspends`, and `in_scenario` take one operand; `implies` takes two; `and`/`or` take 2–16. `believes`/`suspends` require `observer_id`; `in_scenario` requires `scenario_id`. Maximum depth is 16 and maximum nodes 256. Evaluation returns true, false, or unknown (`None`) when the available state cannot decide a claim.

## Sealed event envelope

```json
{"stream":"story","branch_id":"main","sequence":1,"schema_version":2,
 "payload":{"title":"…","source_kind":"authored"},"event_id":"evt_…","integrity_hash":"…"}
```

The event ID and integrity hash derive from the canonical envelope body. `event_id` is a stable prefix of the hash; `integrity_hash` is the full SHA-256 hex digest. Opening/reading a stream verifies both.

Version-1 story/discourse events are up-cast in memory with `source_kind: authored`; their stored lines and IDs remain unchanged. Newly sealed events use version 2. Project metadata remains format version 1.

## Common domain errors

| Code | Meaning / action |
|---|---|
| `E-FIXTURE-001`, `E-CONTRACT-001` | Correct fixture cast/IDs or contract fields |
| `E-STORY-001`, `E-DISCOURSE-001` | Correct event/act fields or references |
| `E-ACCESS-001` | Add observer/access path or accessible belief evidence |
| `E-DISCLOSURE-001` | Ground a reveal or fix withhold order |
| `E-FORMULA-001` | Correct a bounded formula AST |
| `E-DRAFT-001`, `E-GRAPH-001` | Fix draft fields/edges before seal |
| `E-STORE-001`, `E-SCHEMA-001` | Stream failed integrity/schema validation; restore a valid backup |
| `E-LOCK-001` | Close the other writer before opening the project |
| `E-RUN-001`, `E-EXPORT-001` | Match branch/condition or run before export |

The sidecar's `error.data` includes `cmne_code`, `field_path`, `next_action`, and `cause` for domain errors. `command.submit` can instead report a rejected command inside a successful RPC result.

The [generated error catalog](error-catalog.md) lists every current domain code, cause, and next action.
