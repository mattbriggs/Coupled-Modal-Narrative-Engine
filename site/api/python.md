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
| `compare(left, right)` | Two branch IDs | Shared/diverging counts and hashes |

Use `expected_sequence` for optimistic concurrency on append. Sealed history is verified when read and stored atomically when written.

## Draft, graph, and run methods

| Method | Purpose |
|---|---|
| `draft_create(branch, lens)` | Create empty `story` or `discourse` draft |
| `draft_get(draft_id)` / `draft_save(draft)` | Read or replace a draft JSON document |
| `draft_preview(draft)` / `draft_seal(draft_id)` | Validate and append draft events |
| `validate_connection(branch, lens, source, target, kind, draft=None)` | Check a draft edge |
| `graph(lens, branch, draft_id=None, sequence=None, discourse_index=None)` | Lens graph envelope |
| `trace(branch, node_id)` | Causal/disclosure/interpretation details |
| `run(branch, conditions=None)` | Synchronous run and persisted packet/result |
| `list_runs()` | Saved run records in sequence order |

`draft_seal` returns `accepted`, `errors`, `emitted_events`, and `id_map`. A rejected preview does not append events. `run` returns `status`, `prose`, `findings`, `stages`, packet/projection hashes, and IDs; a failed run is still saved.

## Pure functions

`cmne.core` provides `validate_fixture`, `validate_contract`, `validate_story_event`, `validate_discourse_act`, `replay`, `build_packet`, `template_realize`, `check_realization`, `canonical`, `digest`, and `stable_id`. `cmne.formula` provides `validate`, `evaluate`, and `EvaluationContext`. They accept JSON-compatible dictionaries/lists and return JSON-compatible values, except formula evaluation returns `True`, `False`, or `None`. Validation raises `CmneError` with `code`, `field_path`, and `next_action`; the sidecar serializes it as RPC error data.

These functions are the current Python interfaces, not a separate network service. For the exact field shapes, see [Data contracts](contracts.md).
