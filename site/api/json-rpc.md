# JSON-RPC sidecar

`cmne-sidecar` (or `python -m cmne_sidecar.server`) reads one JSON-RPC 2.0 request per input line and writes one response per output line. Keep one process open for a sequence of calls. `app.hello` must succeed before other methods; it accepts protocol major version `1` and returns version, schema, package, and lens names. Standard output is protocol only; diagnostics use standard error.

```json
{"jsonrpc":"2.0","id":1,"method":"app.hello","params":{"protocol_version":"1.0"}}
```

```json
{"jsonrpc":"2.0","id":1,"result":{"protocol_version":"1.0","schema_version":1,"package_version":"…","lenses":["fixture","story","discourse","mind","provenance","motif","pipeline"]}}
```

## Project and validation

| Method | Parameters | Result |
|---|---|---|
| `project.create` | `path` required; `name`, `sample` optional | Project summary |
| `project.sample` | Optional `path`; defaults to Documents/CMNE/Mara and Len | Opens or seeds sample; summary |
| `project.open` | `path` | Project summary |
| `project.close` | — | `{ "closed": true }` |
| `project.get` | — | Project summary |
| `fixture.validate` / `contract.validate` | `fixture` / `contract` | Validated object with `content_hash`; no open project required |
| `fixture.get` / `contract.get` | — | Current object |
| `fixture.save` / `contract.save` | `fixture` / `contract` | Validated and saved object |

The summary has `path`, `name`, `active_branch`, `branches`, `fixture`, and `contract`. Saving fixture/contract updates the current project document; it does not rewrite already sealed events.

## Branch, events, and graph

All branch-aware methods accept optional `branch_id`; omitted means the metadata's active branch, or `main`.

| Method | Other parameters | Result |
|---|---|---|
| `branch.list` | — | Branch metadata array |
| `branch.fork` | `sequence` required; `name` optional | New `branch_id`, `fork_sequence`, `draft_id` |
| `branch.compare` | `left`, `right` | Shared prefix, first divergence, unique counts, hashes |
| `events.read` | `stream` optional, default `story` | Verified event array |
| `command.submit` | `stream` (`story`/`discourse`), `payload`, optional `expected_sequence` | `accepted`, `emitted_events`, `rejected_reason`, invariant results, before/after hashes |
| `graph.get` | `lens`, optional `draft_id`, `sequence`, `discourse_index` | Lens graph envelope |
| `graph.validate_connection` | `lens`, `source`, `target`, `kind`, optional `draft` | `{accepted, reason}` |
| `scrub.projection` | Optional `sequence`, `discourse_index` | Six projections and hashes |
| `overlay.series` / `strain.series` | — | Tension projection, including `series` |
| `trace.query` | `node_id` | Causal parents, observers, disclosures, interpretations |

`command.submit` returns `accepted: false` for a narrative validation rejection rather than an RPC error. Check that field before assuming the event was appended.

## Drafts

| Method | Parameters | Result |
|---|---|---|
| `draft.create` | Optional `lens` (`story` by default) | Empty draft |
| `draft.get` | `draft_id` | Draft JSON |
| `draft.patch` | `draft` | Saved draft JSON |
| `draft.compile_preview` | `draft` or `draft_id` | `{accepted, errors, count}` |
| `draft.seal` | `draft_id` | `{accepted, errors, emitted_events, id_map}` |
| `draft.delete` | `draft_id` | `{deleted: true}` |

A draft contains `id`, `branch_id`, `lens`, `nodes`, and `edges`. Node entries have `id`, `title`, and `fields`; edge entries have `source`, `target`, and `kind` (`causes` for story or `refs` for discourse). Preview and seal validate references, fields, and graph rules. Story draft seals in causal order; discourse draft seals in node ID order when no causal dependencies exist.

## Run and export

| Method | Parameters | Result |
|---|---|---|
| `packet.build` / `packet.get` | Optional `branch_id` | Current computed packet; these do not read an archived packet by hash |
| `run.start` | Optional `branch_id`, `conditions` | One run; or `{runs, status}` for exactly `C0,C1,C2,C3` |
| `run.status` | Optional `branch_id` | Latest saved run or idle status |
| `run.cancel` | — | `{cancelled:false, reason:…}` because runs are synchronous |
| `export.report` | Optional `branch_id` | `{path}` for latest run's Markdown report |

For a single run, the condition must match the selected branch's condition. To run all four sample branches, pass `conditions: ["C0","C1","C2","C3"]` in that order. `export.report` requires a saved run for that branch.

## Errors

```json
{"jsonrpc":"2.0","id":2,"error":{"code":-32000,"message":"…","data":{"cmne_code":"E-STORY-001","field_path":"title","next_action":"…","cause":"…"}}}
```

`-32000` wraps a `CmneError`; `-32602` indicates invalid parameters; `-32700` indicates invalid JSON; `-32603` is an internal sidecar error. The `cmne_code` gives the domain-specific cause. Unknown methods yield `E-RPC-001`. See [Data contracts and errors](contracts.md).
