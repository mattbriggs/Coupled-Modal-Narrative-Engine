# Python kernel

Install the project in a virtual environment as described in [Install and launch](../getting-started/install.md). Imports below use the installed `cmne` package.

```python
from cmne.project import Project

project = Project.create("/tmp/my-scene", "My scene")
try:
    story = project.append_story("main", {
        "title": "The letter arrives",
        "kind": "action",
        "actor_ids": ["actor_a"],
        "description": "A letter arrives at the door."
    })
    project.append_discourse("main", {
        "title": "Opening",
        "mode": "scene",
        "story_refs": [story["event_id"]],
        "text": "A letter waited at the door."
    })
    result = project.run("main")
    print(result["status"], result["prose"])
finally:
    project.close()
```

## `Project` lifecycle and storage

| Method | Inputs | Result |
|---|---|---|
| `Project.create(root, name, sample=False)` | Empty project path; optional seeded sample | Open `Project` |
| `Project(root)` | Existing project path | Open and lock project |
| `close()` | — | Releases writer lock |
| `branch_ids()` | — | List of branch IDs |
| `events(branch, stream)` | Stream `story`, `discourse`, or `evaluation` | Verified event list |
| `append_story(branch, payload, expected_sequence=None)` | Valid story payload | Sealed event |
| `append_discourse(branch, payload, expected_sequence=None)` | Valid discourse payload | Sealed event |
| `projection(branch, sequence=None, discourse_index=None)` | Optional prefixes | `projections` and `hashes` |
| `fork(branch, sequence, name)` | Existing branch and story prefix length | New branch ID and suffix `draft_id` |
| `compare(left, right)` | Two branch IDs | Shared prefix, transition histories, changed interpretations, hashes |
| `motif_ledger(branch)` | Branch ID | Discourse appearances, salience, interpretation links |

Use `expected_sequence` for optimistic concurrency on append. Sealed history is verified when read and stored atomically when written.

## Draft, graph, and run methods

| Method | Purpose |
|---|---|
| `draft_create(branch, lens)` | Create empty `story` or `discourse` draft |
| `draft_get(draft_id)` / `draft_save(draft)` | Read or replace a draft JSON document |
| `draft_preview(draft)` / `draft_seal(draft_id)` | Validate and append draft events |
| `validate_connection(branch, lens, source, target, kind, draft=None)` | Check a draft edge |
| `graph(lens, branch, draft_id=None, sequence=None, discourse_index=None)` | Lens graph envelope |
| `trace(branch, node_id, query="event", **params)` | Event/proposal, actor-belief, reader-inference, model, or prose-access trace |
| `run(branch, conditions=None, variant_index=0)` | Synchronous offline run and persisted candidate/findings |
| `list_runs()` | Saved run records in sequence order |
| `save_analysis_plan(plan)` / `analysis_plan()` | Freeze or read the study plan; amendments cite a prior hash |
| `generate_matched_realizations()` | Save three deterministic composition variants for each condition |
| `study_metrics(branch)` / `study_ablations(branch)` | Layer A/B diagnostics and seven analysis-only variants |
| `realize_ablations(branch)` | Save seven controlled comparison passages, lineage hashes, and checker findings without changing canon |
| `export_evaluation_set(seed=33)` | Randomized public set and separate private key |
| `import_responses(study_id, source)` | Atomically validate and save a response batch |
| `analysis_report(study_id)` | Descriptive report with intervals, agreement, contrary/null sections |
| `decision_packet(study_id)` | Hashed structural/study/ablation evidence for later human review |

`draft_seal` returns `accepted`, `errors`, `emitted_events`, and `id_map`. A rejected preview does not append events. `run` returns `status`, `prose`, `findings`, `stages`, packet/projection hashes, and IDs; a failed run is still saved.

## Pure functions

`cmne.core` provides `validate_fixture`, `validate_contract`, `validate_story_event`, `validate_discourse_act`, `replay`, `build_packet`, `template_realize`, `check_realization`, `canonical`, `digest`, and `stable_id`. `cmne.machines` provides weighted strain, crisis assessment, modal revision, and epiphany-candidate functions. `cmne.prose` provides the `ProseRealizer` protocol and sentence checker. `cmne.study` provides analysis-plan, blind-set, response, and report functions. `cmne.formula` provides `validate`, `evaluate`, and `EvaluationContext`. Validation raises `CmneError` with `code`, `field_path`, and `next_action`; the sidecar serializes it as RPC error data.

These functions are the current Python interfaces, not a separate network service. For the exact field shapes, see [Data contracts](contracts.md).
