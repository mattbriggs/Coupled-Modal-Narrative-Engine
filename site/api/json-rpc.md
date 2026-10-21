# JSON-RPC sidecar

`cmne-sidecar` (or `python -m cmne_sidecar.server`) reads one JSON-RPC 2.0 request per input line and writes one response per output line. Keep one process open for a sequence of calls. `app.hello` must succeed before other methods; it accepts protocol major version `1` and returns version, schema, package, and lens names. Standard output is protocol only; diagnostics use standard error.

```json
{"jsonrpc":"2.0","id":1,"method":"app.hello","params":{"protocol_version":"1.0"}}
```

```json
{"jsonrpc":"2.0","id":1,"result":{"protocol_version":"1.0","schema_version":2,"package_version":"…","lenses":["fixture","story","discourse","mind","provenance","motif","pipeline"]}}
```

## Project and validation

| Method | Parameters | Result |
|---|---|---|
| `project.create` | `path` required; `name`, `sample` optional | Project summary |
| `project.sample` | Optional `path`; defaults to Documents/CMNE/Mara and Len | Opens or seeds sample; summary |
| `project.open` | `path`; optional `read_only: true` | Project summary; read-only opens can coexist with a writer. A failed switch retains the previous project. Close before changing one project's access mode. |
| `project.clear_stale_lock` | `path` | `{cleared: true}` only when a same-host lock owner is no longer running |
| `project.close` | — | `{ "closed": true }` |
| `project.get` | — | Project summary |
| `fixture.validate` / `contract.validate` | `fixture` / `contract` | Validated object with `content_hash`; no open project required |
| `fixture.get` / `contract.get` | — | Current object |
| `fixture.save` / `contract.save` | `fixture` / `contract` | Validated and saved object |
| `fixture.import` / `contract.import` | `path` to a JSON file | Validated and saved object; unsafe paths, symlinks, YAML, and oversized files are refused |

The summary has `path`, `name`, `active_branch`, `branches`, `fixture`, and `contract`. Saving a fixture or contract revalidates sealed story events and preconditions before replacing the file; an incompatible crisis threshold or other rule is rejected without changing the old contract. Neither save rewrites sealed events. Mutating methods refuse a read-only project.

## Branch, events, and graph

All branch-aware methods accept optional `branch_id`; omitted means the metadata's active branch, or `main`.

| Method | Other parameters | Result |
|---|---|---|
| `branch.list` | — | Branch metadata array |
| `branch.fork` | `sequence` required; `name` optional | New `branch_id`, `fork_sequence`, `draft_id` |
| `branch.compare` | `left`, `right` | Shared prefix, state-transition histories, changed interpretations, hashes |
| `events.read` | `stream` optional, default `story` | Verified event array |
| `command.submit` | `stream` (`story`/`discourse`), either `payload` or nonempty `payloads`, optional `expected_sequence` | `accepted`, `emitted_events`, `rejected_reason`, invariant results, before/after hashes |
| `graph.get` | `lens`, optional `draft_id`, `sequence`, `discourse_index` | Lens graph envelope |
| `graph.validate_connection` | `lens`, `source`, `target`, `kind`, optional `draft` | `{accepted, reason}` |
| `scrub.projection` | Optional `sequence`, `discourse_index` | Six projections and hashes |
| `overlay.series` / `strain.series` | — | Tension projection, including `series` |
| `trace.query` | `node_id`; optional `query`, `actor_id`, `claim`, `model_version` | Event/proposal provenance, actor belief, reader inference, model change, or prose access |

`command.submit` validates every payload in a same-stream batch before one atomic stream replacement. Later payloads can depend on earlier payloads in that batch. If any fails, none is appended. It returns `accepted: false` for a pre-commit narrative validation rejection. A storage or projection error after an append can return an RPC error even when the event committed; inspect `events.read` before retrying. Never infer rejection from a post-commit error.

## Drafts

| Method | Parameters | Result |
|---|---|---|
| `draft.create` | Optional `lens` (`story` by default) | Empty draft |
| `draft.get` | `draft_id` | Draft JSON |
| `draft.list` | `branch_id`; optional `lens` (`story` by default) | Recoverable drafts for that branch/lens, newest first |
| `draft.patch` | `draft` | Saved draft JSON |
| `draft.compile_preview` | `draft` or `draft_id` | `{accepted, errors, count}` |
| `draft.seal` | `draft_id` | `{accepted, errors, emitted_events, id_map}` |
| `draft.delete` | `draft_id` | `{deleted: true}` |

A draft contains `id`, `branch_id`, `lens`, `nodes`, and `edges`. Node entries have `id`, `title`, and `fields`; edge entries have `source`, `target`, and `kind` (`causes` for story or `refs` for discourse). Preview and seal validate references, fields, and graph rules. Story draft seals in causal order; discourse draft seals in node ID order when no causal dependencies exist.

`draft.list` reads validated draft files on disk. The workbench uses it to recover a draft when its browser local-storage pointer is unavailable after a crash or reset.

## Run and export

| Method | Parameters | Result |
|---|---|---|
| `packet.build` / `packet.get` | Optional `branch_id` | Current computed packet; these do not read an archived packet by hash |
| `run.start` | Optional `branch_id`, `conditions`, `variant_index`, `async: true` | Saved run(s), or `{job_id, status, total}` for a background run |
| `run.status` | Optional `branch_id` or `job_id` | Latest saved run, or background progress and completed runs |
| `run.cancel` | — | Requests cancellation at the next condition boundary |
| `export.report` | Optional `branch_id` | `{path}` for latest run's Markdown report |

For a single run, the condition must match the selected branch's condition. To run all four sample branches, pass `conditions: ["C0","C1","C2","C3"]` in that order. `export.report` requires a saved run for that branch.

`async: true` returns promptly. Poll `run.status` with the returned `job_id`; its `completed` and `total` fields show condition progress. Each status result is a snapshot, so its run list will not change after the response is returned. `run.cancel` stops before the next condition, without changing sealed story or discourse. Read-only graph/event queries and draft editing remain available while a run is active; canon, fixture, contract, study, and export mutations are refused until it finishes.

## Blinded study

| Method | Parameters | Result |
|---|---|---|
| `study.plan.save` / `study.plan.get` | `plan` for save | Frozen plan, hash, creation time, and optional prior-plan hash |
| `study.generate` | — | Three deterministic composition variants for each C0–C3 branch |
| `study.metrics` | Optional `branch_id` | Layer A blocking and Layer B descriptive measures |
| `study.ablations` | Optional `branch_id` | Seven analysis-only ablation descriptions and hashes |
| `study.ablations.realize` | Optional `branch_id` | Seven saved controlled passages, packet/text hashes, and findings; canon unchanged |
| `study.export` | Optional integer `seed` | Public folder, private key path, study ID, passage count |
| `study.responses.import` | `study_id` and `path` or `responses` document | Validated batch count; malformed batches make no changes |
| `study.report` | `study_id` | Saved descriptive report, including null and contrary results |
| `study.decision_packet` | `study_id` | Saved hashed evidence packet; human decision remains pending |

The public evaluation folder includes an accessible HTML protocol and passages. The condition key lives under `study/keys/` and should not be shared with evaluators. See [the evaluation procedure](../manual/evaluate-study.md).

## Errors

```json
{"jsonrpc":"2.0","id":2,"error":{"code":-32000,"message":"…","data":{"cmne_code":"E-STORY-001","field_path":"title","next_action":"…","cause":"…"}}}
```

`-32000` wraps a `CmneError`; `-32602` indicates invalid parameters (including a non-object `params` value); `-32700` indicates invalid JSON; `-32603` is an internal sidecar error. A non-object request receives `E-PROTO-001`. The `cmne_code` gives the domain-specific cause. Unknown methods yield `E-RPC-001`. See [Data contracts and errors](contracts.md).
